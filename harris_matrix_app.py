import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import fontManager, FontProperties
from io import BytesIO
import plotly.graph_objects as go
matplotlib.use("Agg")

# 设置默认字体
font_path = "simhei.ttf"
fontManager.addfont(font_path)
font_name = FontProperties(fname=font_path).get_name()
matplotlib.rcParams['font.family'] = font_name

# Streamlit 页面设置
st.set_page_config(page_title="Harris Matrix Viewer", layout="wide")
st.title("地层关系计算器")

st.markdown("""
### 使用说明
欢迎使用地层关系计算器^ ^！
- 上传你的地层关系 CSV 文件，或使用示例数据（新地里墓地部分打破关系）。
- 根据你的CSV文件里的地层关系，这里可以查询里面任意两个单位的相对关系（它们也可能没有关系）。
- 图中单位节点大致按照地层早晚关系排布，但不绝对，请以具体查询为准。查询到的路径里上面的节点晚，下面的节点早。
- 左侧边栏可调节圆点大小、字体和箭头线条粗细。
- 支持高亮路径查询与图像下载。
- 祝你读报告顺利！
""")

# 选择数据源
st.subheader("数据来源")
data_choice = st.radio("请选择", ["使用示例数据", "上传 CSV 文件或在线填写数据"])
if data_choice == "上传 CSV 文件或在线填写数据":
    st.markdown("""
    ### 使用说明
    
    如果选择上传CSV文件，请使用excel写地层单位表格，保存成CSV文件。  \n
    或者可以填写下方在线表格。  \n
    表格应当包含later和earlier两列，也就是第一行表头写later,﻿earlier，之后每行写两个单位，就标注了这两个单位的关系，前面的叠压打破后面的。如果想说“M86开口6层下，打破M99和第7层”你的CSV 文件应该长成这样：  \n
    later,earlier  \n
    6层,M86  \n
    M86,M99  \n
    M86,7层  \n
    6层,7层  \n
    ……  \n
    请注意，不可以出现循环结构，如：M14→M19→M14。
    试试吧！  \n
    ---
    ### 上传 CSV 文件
    """)
    uploaded_file = st.file_uploader("上传 CSV 文件（包含 later 和 earlier 列）", type="csv")
    st.markdown("""
    ---
    ### 在线编辑地层关系表格
    或者你也可以直接在下方在线填写关系对：
    """)
    # 初始设置只运行一次
    if "editable_df" not in st.session_state:
        st.session_state.editable_df = pd.DataFrame({"Later": [""], "Earlier": [""]})
    
    # 允许用户编辑表格，限制为两列
    edited_df = st.data_editor(
        st.session_state["editable_df"],
        column_config={
            "Later": st.column_config.TextColumn("Later"),
            "Earlier": st.column_config.TextColumn("Earlier")
        },
        num_rows="dynamic",
        use_container_width=True,
        key="inline_editor"
    )
    
    if st.button("加载上方表格为数据"):
        st.session_state["editable_df"] = edited_df.copy()
        st.session_state["loaded_df"] = edited_df.copy()
        st.success("数据已加载！")
        st.rerun()
else:
    uploaded_file = "新地里地层关系.csv"

st.sidebar.header("图形参数调节")
node_size = st.sidebar.slider("节点大小", 500, 5000, 1300, step=100)
font_size = st.sidebar.slider("字体大小", 6, 30, 16, step=1)
arrow_width = st.sidebar.slider("箭头线条粗细", 0.5, 10.0, 1.5, step=0.5)

if uploaded_file is not None or st.session_state.get("loaded_df") is not None:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file else st.session_state.loaded_df.copy()
        df.columns = df.columns.str.encode('utf-8').str.decode('utf-8-sig').str.strip().str.capitalize()
        if 'Later' not in df.columns or 'Earlier' not in df.columns:
            st.error("CSV 文件必须包含 'Later' 和 'Earlier' 两列")
        else:
            G = nx.DiGraph()
            edges = list(zip(df['Later'], df['Earlier']))
            G.add_edges_from(edges)

            depths = {}
            for node in nx.topological_sort(G):
                preds = list(G.predecessors(node))
                depths[node] = 0 if not preds else max(depths[p] + 1 for p in preds)

            layers = {}
            for node, d in depths.items():
                layers.setdefault(d, []).append(node)

            spacing, layer_spacing = 4.0, 2.5
            pos = {}
            for layer, nodes in layers.items():
                for i, node in enumerate(nodes):
                    x = (i - (len(nodes) - 1) / 2) * spacing
                    y = -layer * layer_spacing
                    pos[node] = (x, y)

            st.subheader("地层关系查询")
            node_list = list(G.nodes)
            
            # 如果之前保存的 unit1 不在当前节点中，就重设
            if "unit1" not in st.session_state or st.session_state.unit1 not in node_list:
                st.session_state.unit1 = node_list[0]
            if "unit2" not in st.session_state or st.session_state.unit2 not in node_list:
                st.session_state.unit2 = node_list[min(1, len(node_list)-1)]

            try:
                longest_path = nx.dag_longest_path(G)
                if st.button("加载最典型的一组叠压打破关系"):
                    st.session_state.unit1, st.session_state.unit2 = longest_path[0], longest_path[-1]
                    st.rerun()
            except nx.NetworkXUnfeasible:
                st.warning("图中存在环，无法计算最长路径")

            unit1 = st.selectbox("选择起点单位", node_list, index=node_list.index(st.session_state.unit1), key="select_unit1")
            highlight_all = st.checkbox("高亮所有经过起点单位的地层关系")

            def check_relation(u1, u2):
                if u2 is None:
                    return [], ""
                if nx.has_path(G, u1, u2):
                    return list(nx.all_simple_paths(G, source=u1, target=u2)), f"地层关系：{u1} 比 {u2} 更晚"
                elif nx.has_path(G, u2, u1):
                    return list(nx.all_simple_paths(G, source=u2, target=u1)), f"地层关系：{u2} 比 {u1} 更晚"
                return [], f"{u1} 和 {u2} 之间无地层早晚关系"

            if highlight_all:
                all_paths, unit2 = [], None
                seen = set()
                for source in G.nodes:
                    for target in G.nodes:
                        if source != target and nx.has_path(G, source, target):
                            for path in nx.all_simple_paths(G, source=source, target=target):
                                if unit1 in path:
                                    t = tuple(path)
                                    if not any(set(t).issubset(set(p)) for p in seen):
                                        seen.add(t)
                all_paths = list(seen)
                relation_text = f"所有经过 {unit1} 的路径（共 {len(all_paths)} 条，已去除包含关系）"
            else:
                unit2 = st.selectbox("选择终点单位", node_list, index=node_list.index(st.session_state.unit2), key="select_unit2")
                all_paths, relation_text = check_relation(unit1, unit2)

            st.markdown(f"**{relation_text}**")

            highlight_edges = {(path[i], path[i+1]) for path in all_paths for i in range(len(path)-1)}
            highlight_nodes = {node for path in all_paths for node in path}
            highlight_nodes.update([unit1] + ([unit2] if unit2 else []))

            fig_width = min(max(5, spacing * max(len(v) for v in layers.values())), 30)
            fig_height = min(max(3, layer_spacing * len(layers)), 20)

            # 构建 Plotly 图形数据
            edge_x, edge_y = [], []
            highlight_edge_x, highlight_edge_y = [], []
            
            for edge in G.edges():
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                coords = [x0, x1, None], [y0, y1, None]
                if edge in highlight_edges:
                    highlight_edge_x += coords[0]
                    highlight_edge_y += coords[1]
                else:
                    edge_x += coords[0]
                    edge_y += coords[1]
            
            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=arrow_width, color='#888'),
                hoverinfo='none',
                mode='lines'
            )
            
            highlight_edge_trace = go.Scatter(
                x=highlight_edge_x, y=highlight_edge_y,
                line=dict(width=arrow_width + 1.5, color='red'),
                hoverinfo='none',
                mode='lines'
            )
            
            node_x, node_y, node_color, node_text = [], [], [], []
            for node in G.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)
                node_color.append('orange' if node in highlight_nodes else 'lightblue')
                node_text.append(node)
            
            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode='markers+text',
                text=node_text,
                textposition='middle center',
                hoverinfo='text',
                marker=dict(
                    color=node_color,
                    size=node_size // 100,
                    line_width=2
                )
            )
            
            fig = go.Figure(data=[edge_trace, highlight_edge_trace, node_trace],
                            layout=go.Layout(
                                showlegend=False,
                                hovermode='closest',
                                margin=dict(b=20, l=5, r=5, t=40),
                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                height=int(fig_height * 100),
                                width=int(fig_width * 100),
                                dragmode='pan'
                            ))
            for edge in G.edges():
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                is_highlighted = edge in highlight_edges
                fig.add_annotation(
                    ax=x0, ay=y0,
                    x=x1, y=y1,
                    xref='x', yref='y',
                    axref='x', ayref='y',
                    showarrow=True,
                    arrowhead=2,           # 箭头样式
                    arrowsize=1.2,         # 箭头大小
                    arrowwidth=2.5 if is_highlighted else 1.5,
                    arrowcolor='red' if is_highlighted else '#888',
                    opacity=1
                )    
            st.plotly_chart(fig, use_container_width=True)    
            
            if all_paths:
                st.markdown("**所有可能路径：**")
                for path in all_paths:
                    st.markdown(" → ".join(path))

            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
            buf.seek(0)
            st.download_button("📥下载为 PNG 图像", data=buf, file_name="harris_matrix.png", mime="image/png")

    except Exception as e:
        st.error(f"❌ 无法读取文件：{e}")
