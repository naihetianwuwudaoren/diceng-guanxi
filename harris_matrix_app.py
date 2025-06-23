import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import fontManager, FontProperties
from io import BytesIO
matplotlib.use("Agg")

# 设置默认字体
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
- 上传你的地层路径式 CSV 文件（每行表示一条地层路径，如 M86,M99,6层）。
- 系统会自动转为节点关系图，图中单位节点大致按照地层早晚关系排布。
- 支持查询两个单位的相对关系，或高亮所有经过某单位的路径。
- 左侧边栏可调节节点大小、字体和箭头粗细。
- 支持图像下载。
你也可以在下方通过表格填写路径：每行表示一条路径，列依次填入单位。
""")

st.subheader("上传或填写路径数据")
uploaded_file = st.file_uploader("上传 CSV 文件（每行一条路径，单位用逗号分隔，如 M86,M99,6层）", type="csv")

st.markdown("或使用下方表格在线填写路径（每行一条路径，列为依次单位）")
if "path_table" not in st.session_state:
    st.session_state.path_table = pd.DataFrame([["", ""]], columns=["Unit 1", "Unit 2"])

editable_df = st.data_editor(
    st.session_state.path_table,
    num_rows="dynamic",
    use_container_width=True,
    key="path_editor"
)

if st.button("加载上方路径表格为数据"):
    st.session_state.path_table = editable_df.copy()
    st.session_state["path_text"] = ""  # 清除旧文本输入
    st.success("路径数据已加载！")
    st.rerun()

st.sidebar.header("图形参数调节")
node_size = st.sidebar.slider("节点大小", 500, 5000, 1300, step=100)
font_size = st.sidebar.slider("字体大小", 6, 30, 16, step=1)
arrow_width = st.sidebar.slider("箭头线条粗细", 0.5, 10.0, 1.5, step=0.5)

def parse_paths_from_df(df):
    edge_list = []
    for row in df.itertuples(index=False):
        nodes = [str(cell).strip() for cell in row if pd.notna(cell) and str(cell).strip() != ""]
        edge_list.extend([(nodes[i], nodes[i+1]) for i in range(len(nodes) - 1)])
    return edge_list

if uploaded_file or ("path_table" in st.session_state and not st.session_state.path_table.dropna(how="all").empty):
    try:
        if uploaded_file:
            df = pd.read_csv(uploaded_file, header=None)
            edges = parse_paths_from_df(df)
        else:
            edges = parse_paths_from_df(st.session_state.path_table)

        G = nx.DiGraph()
        G.add_edges_from(edges)

        if not nx.is_directed_acyclic_graph(G):
            st.error("❌ 输入图存在环结构，无法构建 Harris Matrix。请检查数据。")
            st.stop()

        G = nx.transitive_reduction(G)

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

        if "unit1" not in st.session_state:
            st.session_state.unit1 = node_list[0]
        if "unit2" not in st.session_state:
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
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        for (u, v) in G.edges:
            is_highlight = (u, v) in highlight_edges
            color = 'red' if is_highlight else 'gray'
            width = narrow_width + 1.5 if is_highlight else narrow_width
            alpha = 1.0 if is_highlight else 0.6

            ax.annotate("",
                xy=pos[v], xycoords='data',
                xytext=pos[u], textcoords='data',
                arrowprops=dict(
                    arrowstyle='-|>',
                    color=color,
                    lw=width,
                    shrinkA=15, shrinkB=15,
                    mutation_scale=20,
                    alpha=alpha
                )
            )

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
        fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
        buf.seek(0)
        st.download_button("📥下载为 PNG 图像", data=buf, file_name="harris_matrix.png", mime="image/png")

    except Exception as e:
        st.error(f"❌ 无法读取数据：{e}")
