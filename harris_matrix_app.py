import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import fontManager, FontProperties
from io import BytesIO

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
欢迎使用地层关系计算器 ^ ^！
- 上传你的 CSV 地层关系表格，或使用示例数据
- 可查询任意两个单位的相对时间关系
- 图中节点大致按时间排列，但不精确，请以查询为准
- 支持高亮路径和下载图像
""")

# 选择数据源
st.subheader("数据来源")
data_choice = st.radio("请选择", ["使用示例数据", "上传 CSV 文件"])
if data_choice == "上传 CSV 文件":
    uploaded_file = st.file_uploader("上传 CSV 文件（包含 later 和 earlier 列）", type="csv")
else:
    uploaded_file = "新地里地层关系.csv"

st.sidebar.header("图形参数调节")
node_size = st.sidebar.slider("节点大小", 500, 5000, 1300, step=100)
font_size = st.sidebar.slider("字体大小", 6, 30, 16, step=1)
arrow_width = st.sidebar.slider("箭头线条粗细", 0.5, 10.0, 1.5, step=0.5)

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
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
            st.session_state.unit1 = st.session_state.get("unit1", node_list[0])
            st.session_state.unit2 = st.session_state.get("unit2", node_list[min(1, len(node_list)-1)])

            try:
                longest_path = nx.dag_longest_path(G)
                if st.button("\U0001F4CC加载图中最长路径为查询节点"):
                    st.session_state.unit1, st.session_state.unit2 = longest_path[0], longest_path[-1]
                    st.rerun()
            except nx.NetworkXUnfeasible:
                st.warning("图中存在环，无法计算最长路径")

            unit1 = st.selectbox("选择起点单位", node_list, index=node_list.index(st.session_state.unit1), key="select_unit1")
            highlight_all = st.checkbox("✨高亮所有从起点出发的路径")

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
                for target in G.nodes:
                    if target != unit1 and nx.has_path(G, unit1, target):
                        all_paths.extend(list(nx.all_simple_paths(G, source=unit1, target=target)))
                relation_text = f"所有从 {unit1} 出发的路径（共 {len(all_paths)} 条）"
            else:
                unit2 = st.selectbox("选择终点单位", node_list, index=node_list.index(st.session_state.unit2), key="select_unit2")
                all_paths, relation_text = check_relation(unit1, unit2)

            st.markdown(f"**{relation_text}**")

            highlight_edges = {(path[i], path[i+1]) for path in all_paths for i in range(len(path)-1)}
            highlight_nodes = {node for path in all_paths for node in path}
            highlight_nodes.update([unit1] + ([unit2] if unit2 else []))

            fig_width = min(max(5, spacing * max(len(v) for v in layers.values())), 30)
            fig_height = min(max(3, layer_spacing * len(layers)), 20)
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))

            nx.draw_networkx_edges(G, pos, edgelist=[e for e in G.edges if e not in highlight_edges], width=narrow_width, edge_color='gray', arrows=True, arrowstyle='-|>', ax=ax)
            nx.draw_networkx_edges(G, pos, edgelist=list(highlight_edges), width=narrow_width+1.5, edge_color='red', arrows=True, arrowstyle='-|>', ax=ax)

            nx.draw_networkx_nodes(G, pos, nodelist=[n for n in G.nodes if n not in highlight_nodes], node_color='lightblue', node_size=node_size, ax=ax)
            nx.draw_networkx_nodes(G, pos, nodelist=list(highlight_nodes), node_color='orange', node_size=node_size+200, ax=ax)
            nx.draw_networkx_labels(G, pos, font_size=font_size, font_family=font_name, ax=ax)
            ax.axis('off')

            st.pyplot(fig)
            if all_paths:
                st.markdown("**所有可能路径：**")
                for path in all_paths:
                    st.markdown(" → ".join(path))

            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
            buf.seek(0)
            st.download_button("📥下载为 PNG 图像", data=buf, file_name="harris_matrix.png", mime="image/png")

    except Exception as e:
        st.error(f"❌ 无法读取文件：{e}")
