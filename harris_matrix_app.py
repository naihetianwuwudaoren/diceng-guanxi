import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import fontManager, FontProperties
from io import BytesIO
import json
from streamlit.components.v1 import html
import inspect
from st_link_analysis import st_link_analysis
from st_link_analysis.component.styles import NodeStyle, EdgeStyle


# 先造一个极简的 test 元素（2 个节点 + 1 条边）
elements = {
    "nodes": [
        {"data": {"id": "A", "label": "A"}},
        {"data": {"id": "B", "label": "B"}},
    ],
    "edges": [
        {"data": {"id": "A__B", "source": "A", "target": "B"}},
    ]
}

# 常见内置布局名
candidates = [
    "grid",
    "random",
    "circle",
    "concentric",
    "breadthfirst",
    "cose",
    "preset",
]

supported = []
for name in candidates:
    try:
        st_link_analysis(
            elements=elements,
            layout={"name": name},
            height=200,
            key=f"test_{name}"
        )
        supported.append(name)
    except Exception:
        # 布局名不支持就会抛
        pass

st.write("✅ 支持的布局有：", supported)

font_path = "simhei.ttf"
fontManager.addfont(font_path)
font_name = FontProperties(fname=font_path).get_name()
matplotlib.rcParams['font.family'] = font_name
        

# 页面设置
st.set_page_config(page_title="Harris Matrix Viewer", layout="wide")
st.title("地层关系计算器")

st.markdown("""
### 使用说明
欢迎使用地层关系计算器^ ^！
- 0624新功能！试试看生成子图吧，只看您格外关心的那些单位！
- 0624新功能！查看某个单位与其他所有单位的关系列表，比如一键得到所有比6层更早的单位————然后可以生成它们的子图！
- 上传您的地层路径 CSV 文件，或者先用示例数据玩玩看。
- 系统会自动转为节点关系图，图中单位节点大致按照地层早晚关系排布。
- 支持查询两个单位的相对关系，或高亮所有经过某单位的地层关系路径。
- 左侧边栏可调节节点大小、字体和箭头粗细。
- 您也可以上传关系表格或在下方在线填写地层关系。  \n
祝您啃报告顺利！
""")

# 示例数据
try:
    example_df = pd.read_csv("新地里地层关系.csv", header=None, encoding="utf-8-sig")
except UnicodeDecodeError:
    example_df = pd.read_csv("新地里地层关系.csv", header=None, encoding="gbk")
    
# 选择数据源
st.subheader("数据来源")
data_choice = st.radio("请选择数据来源", ["使用示例数据", "上传 CSV 文件或在线填写地层关系"])

uploaded_file = None
path_df = None
# 替换原有表格读取逻辑：仅在点击按钮并有有效数据后再加载
data_ready = False
if data_choice != "使用示例数据":
    st.markdown("""
    ### 上传您的地层关系CSV文件  \n
    - 可以用excel写，存成CSV，每格一个单位，每行是一条地层关系路径，例如一行的一二三格分别是M86、M99、6层，意为M86→M99→6层。
    - 不写表头，直接写地层关系。
    - 地层关系可以重叠交叉，可以全部串在一起写，也可以拆成一行一行碎的短路径，看您喜欢！
    - 左边晚，右边早。
    - 玩得开心！ 
    """)
    uploaded_file = st.file_uploader("上传 CSV 文件", type="csv")

    st.markdown("""### 在线填写地层关系  \n
    使用下方表格在线填写路径，每格一个单位，每行的左边格子晚，右边格子早""")
    if "path_table" not in st.session_state:
        st.session_state.path_table = pd.DataFrame(
            [["" for _ in range(6)]],
            columns=[f"Unit {i+1}" for i in range(6)]
        )

    editable_df = st.data_editor(
        st.session_state.path_table,
        num_rows="dynamic",
        use_container_width=True,
        key="path_editor"
    )

    if st.button("加载上方路径表格为数据"):
        cleaned = editable_df.dropna(how="all")
        if not cleaned.empty:
            st.session_state.path_table = cleaned.copy()
            data_ready = True
            st.success("路径数据已加载！")
            st.rerun()
        else:
            st.warning("请至少填写一行路径，且该行需包含两个以上单位。")

    if uploaded_file:
        path_df = pd.read_csv(uploaded_file, header=None)
        data_ready = True
    elif data_ready:
        path_df = st.session_state.path_table.copy()

elif data_choice == "使用示例数据":
    path_df = example_df.copy()
    data_ready = True

def parse_paths_from_df(df):
    edge_list = []
    for row in df.itertuples(index=False):
        nodes = [str(cell).strip() for cell in row if pd.notna(cell) and str(cell).strip() != ""]
        if len(nodes) < 2:
            continue  # 跳过不足两个单位的路径，避免报错
        edge_list.extend([(nodes[i], nodes[i+1]) for i in range(len(nodes) - 1)])
    return edge_list

st.sidebar.header("图形参数调节")
node_size = st.sidebar.slider("节点大小", 500, 5000, 1300, step=100)
font_size = st.sidebar.slider("字体大小", 6, 30, 16, step=1)
arrow_width = st.sidebar.slider("箭头线条粗细", 0.5, 10.0, 1.5, step=0.5)

if path_df is not None:
    try:
        edges = parse_paths_from_df(path_df)
        G = nx.DiGraph()
        G.add_edges_from(edges)

        if not nx.is_directed_acyclic_graph(G):
            st.error("❌ 输入图存在环结构，无法构建 Harris Matrix。请检查数据。")
            st.stop()

        G = nx.transitive_reduction(G)
        
        if 'subgraph_mode' not in st.session_state:
            st.session_state.subgraph_mode = False
        if 'sub_nodes' not in st.session_state:
            st.session_state.sub_nodes = []
        
        col_input, col_btn = st.columns([4,1])
        with col_input:
            sub_input = st.text_input(
                "可以挑选一些你感兴趣的单位，显示它们的关系。  \n请输入要生成子图的单位（支持中文逗号、顿号、英文逗号或空格分隔）", 
                value=st.session_state.get("sub_input", ""),
                key="sub_input"
            )

        with col_btn:
            if not st.session_state.subgraph_mode:
                if st.button("生成子图"):
                    # 从 session_state 拿原始字符串
                    raw = sub_input
                    import re
                    # 拆分、strip，并且只保留 G.nodes 里真的存在的
                    normalized = re.sub(r"[，、\s]+", ",", raw.strip())
                    candidates = [tok.strip() for tok in normalized.split(",") if tok.strip()]
                    selected = [tok for tok in candidates if tok in G.nodes]
                    
                    if selected:
                        st.session_state.sub_nodes = selected
                        st.session_state.subgraph_mode = True
                        st.session_state.show_relation = False
                        st.rerun()
                    else:
                        st.warning("⚠️ 子图至少要包含一个有效单位")
            else:
                if st.button("返回完整图"):
                    st.session_state.subgraph_mode = False
                    st.session_state.show_relation = False
                    st.rerun()
        
        # 选出当前要绘制的 Graph
        if st.session_state.subgraph_mode:
            G_draw = G.subgraph(st.session_state.sub_nodes).copy()
            st.markdown(f"**当前子图：{', '.join(st.session_state.sub_nodes)}**")
        else:
            G_draw = G
        
                    
        node_list = list(G_draw.nodes)

            
        st.subheader("地层关系查询")

        if "unit1" not in st.session_state or st.session_state.unit1 not in node_list:
            st.session_state.unit1 = node_list[0]
        if "unit2" not in st.session_state:
            # 如果只有一个节点，就让 unit2 为 None
            st.session_state.unit2 = node_list[1] if len(node_list) > 1 else None
        elif st.session_state.unit2 not in node_list:
            # 如果之前的 unit2 已不在子图里，也重置
            st.session_state.unit2 = node_list[1] if len(node_list) > 1 else None
        if "show_relation" not in st.session_state:
            st.session_state.show_relation = False

        try:
            longest_path = nx.dag_longest_path(G_draw)
            if st.button("加载最长的一组叠压打破关系"):
                st.session_state.unit1, st.session_state.unit2 = longest_path[0], longest_path[-1]
                st.rerun()
        except nx.NetworkXUnfeasible:
            st.warning("图中存在环，无法计算最长路径")
            
        # 构造带“空”选项的列表
        empty_label = "-- 请选择 --"
        unit_options = [empty_label] + list(G_draw.nodes)
        unit1 = st.selectbox("选择起点单位", options=unit_options, index=0, key="select_unit1")
        # 把空标签映射回 None
        if unit1 == empty_label:
            unit1 = None            
            
        if st.button("查询起点单位相关地层关系"):
            st.session_state.show_relation = True
        highlight_all = st.session_state.get("show_relation", False)
        
        unit2 = st.selectbox("选择终点单位", options=unit_options, index=0, key="select_unit2")
        if unit2 == empty_label:
            unit2 = None
        all_paths, relation_text = [], ""
        
        def check_relation(u1, u2):
            if u2 is None:
                return [], ""
            if nx.has_path(G_draw, u1, u2):
                return list(nx.all_simple_paths(G_draw, source=u1, target=u2)), f"地层关系：{u1} 比 {u2} 更晚"
            elif nx.has_path(G_draw, u2, u1):
                return list(nx.all_simple_paths(G_draw, source=u2, target=u1)), f"地层关系：{u2} 比 {u1} 更晚"
            return [], f"{u1} 和 {u2} 之间无地层早晚关系"

        if highlight_all and unit1:
            all_paths, unit2 = [], None
            # 计算和 unit1 的三类关系
            earlier_units   = list(nx.descendants(G_draw, unit1))   # unit1 -> x 即 x 比 unit1 更早
            later_units     = list(nx.ancestors(G_draw, unit1))     # x -> unit1 即 x 比 unit1 更晚
            unrelated_units = [
                n for n in G_draw.nodes 
                if n not in earlier_units 
                and n not in later_units 
                and n != unit1
            ]
            
            # 三列布局展示
            col1, col2, col3 = st.columns(3)
            col1.subheader(f"比 {unit1} 更早的单位")
            col1.write("、".join(earlier_units) if earlier_units else "无")
            col2.subheader(f"比 {unit1} 更晚的单位")
            col2.write("、".join(later_units)   if later_units   else "无")
            col3.subheader(f"与 {unit1} 无直接关系的单位")
            col3.write("、".join(unrelated_units) if unrelated_units else "无")
            with col1:
                if earlier_units:
                    if st.button(f"查看 “比 {unit1} 更早” 子图", key="sub_early"):
                        st.session_state.sub_nodes = earlier_units
                        st.session_state.subgraph_mode = True
                        st.rerun()
            with col2:
                if later_units:
                    if st.button(f"查看 “比 {unit1} 更晚” 子图", key="sub_late"):
                        st.session_state.sub_nodes = later_units
                        st.session_state.subgraph_mode = True
                        st.rerun()
            with col3:

                if unrelated_units:
                    if st.button(f"查看 “与 {unit1} 无关” 子图", key="sub_unrelated"):
                        st.session_state.sub_nodes = unrelated_units
                        st.session_state.subgraph_mode = True
                        st.rerun()
                
            seen = set()
            for source in G_draw.nodes:
                for target in G_draw.nodes:
                    if source != target and nx.has_path(G_draw, source, target):
                        for path in nx.all_simple_paths(G_draw, source=source, target=target):
                            if unit1 in path:
                                t = tuple(path)
                                if not any(set(t).issubset(set(p)) for p in seen):
                                    seen.add(t)
            all_paths = list(seen)
            relation_text = f"所有经过 {unit1} 的路径（共 {len(all_paths)} 条）"
        elif unit1 and unit2:
            all_paths, relation_text = check_relation(unit1, unit2)

        st.markdown(f"**{relation_text}**")
        
        
        highlight_edges = {(path[i], path[i+1]) for path in all_paths for i in range(len(path)-1)}
        highlight_nodes = {node for path in all_paths for node in path}
        highlight_nodes.update([unit1] + ([unit2] if unit2 else []))
            
        highlight_nodes.discard(None)
        highlight_nodes &= set(G_draw.nodes)
        st.write("【调试】G_draw 节点列表：", list(G_draw.nodes()))
 
        nodes = []
        for n in G_draw.nodes():
            # data 里要有 id, label
            node_data = {"id": n, "label": n}
            # 如果在高亮集合里，就在 classes 里标记 "highlight"
            if n in highlight_nodes:
                nodes.append({"data": node_data, "classes": "highlight"})
            else:
                nodes.append({"data": node_data})
        
        # 2) 构造 edges 列表
        edges = []
        for u, v in G_draw.edges():
            # 给每条边一个唯一 id
            edge_id = f"{u}__{v}"
            edge_data = {
                "id": edge_id,
                "source": u,
                "target": v,
                "label": ""   # 如果想在边上显示文字，可以填入这里
            }
            if (u, v) in highlight_edges:
                edges.append({"data": edge_data, "classes": "highlight"})
            else:
                edges.append({"data": edge_data})
        
        # 3) 打包成 elements 字典
        elements = {
            "nodes": nodes,
            "edges": edges
        }
        node_styles = [
            NodeStyle(
                label=str(node),       # 匹配 data["label"] == node
                color="#ADD8E6",       # 节点背景色
                caption="label",       # 用 data["label"] 作为节点文字
                icon=None
            )
            for node in G_draw.nodes()
        ]
        node_styles += [
            NodeStyle(
                label=str(node),
                color="orange",
                caption="label",
                icon=None
            )
            for node in highlight_nodes
        ]
        edge_styles = [
            # 默认所有边灰色有向
            EdgeStyle(
                label="",             # 匹配所有边（data["label"] 你留空）
                color="gray",         # 线条颜色
                directed=True         # 显示箭头
            ),
            # 高亮的边
            EdgeStyle(
                label="",             
                color="red",
                directed=True
            )
        ]
        # 3) 定义 Klay 布局参数
        dagre_layout = {
            "name": "dagre",
            "rankDir": "TB",        # 从上到下
            # 你还可以加 nodeSep, edgeSep, rankSep 等 dagre 特有参数：
            "nodeSep": 50,
            "edgeSep": 10,
            "rankSep": 50,
        }

        klay_layout = {
            "name": "klay",
            "klay": {
                "nodeDimensionsIncludeLabels": True,
                "spacing": 50,
                "edgeSpacingFactor": 0.2,
                "orientation": "DOWN",
                "layering": "INTERACTIVE",
            }
        }
        st.subheader("可交互视图（Klay 布局）")
        st_link_analysis(
            elements=elements,
            layout=dagre_layout,
            node_styles=node_styles,
            edge_styles=edge_styles,
            height=700,
            key="harris-graph"
        )
        if all_paths:
            st.markdown("**所有可能路径：**")
            for path in all_paths:
                st.markdown(" → ".join(path))



    except Exception as e:
        st.error(f"❌ 无法读取数据：{e}")
