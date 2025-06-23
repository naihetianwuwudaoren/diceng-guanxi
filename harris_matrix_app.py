import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import FontProperties
from matplotlib import font_manager
from io import BytesIO

# 加载 .ttf 字体文件（使用你的字体路径）
font_path = "simhei.ttf" 
font_manager.fontManager.addfont(font_path)

# 获取字体名（必要时打印）
font_name = font_manager.FontProperties(fname=font_path).get_name()

# 设置 matplotlib 全局默认字体
matplotlib.rcParams['font.family'] = font_name

# === Streamlit 页面设置 ===
st.set_page_config(page_title="Harris Matrix Viewer", layout="wide")
st.title("地层关系查询工具")

# === 数据选择：上传或使用示例 ===
data_choice = st.radio("请选择数据来源", ["使用示例数据", "上传 CSV 文件"])

if data_choice == "上传 CSV 文件":
    uploaded_file = st.file_uploader("上传 CSV 文件（包含 Earlier 和 Later 列）", type="csv")
else:
    uploaded_file = "新地里地层关系.csv"  # 示例数据的路径

st.sidebar.header("图形参数调节")
node_size = st.sidebar.slider("节点大小", 500, 5000, 2000, step=100)
font_size = st.sidebar.slider("字体大小", 6, 30, 10, step=1)
arrow_width = st.sidebar.slider("箭头粗细", 0.5, 10.0, 1.5, step=0.5)
spacing = 4.0
layer_spacing = 2.5
if uploaded_file:
    try:
        # 读取并标准化列名
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip().str.capitalize()
    
        if 'Earlier' not in df.columns or 'Later' not in df.columns:
            st.error("CSV 文件必须包含 'Earlier' 和 'Later' 两列")
        else:
            # 构建图
            G = nx.DiGraph()
            edges = list(zip(df['Earlier'], df['Later']))
            G.add_edges_from(edges)
    
            # 自动计算节点深度
            depths = {}
            for node in nx.topological_sort(G):
                preds = list(G.predecessors(node))
                depths[node] = 0 if not preds else max(depths[p] + 1 for p in preds)
    
            # 分层分组
            layers = {}
            for node, d in depths.items():
                layers.setdefault(d, []).append(node)
    
            # 坐标计算
            pos = {}
            for layer, nodes in layers.items():
                count = len(nodes)
                for i, node in enumerate(nodes):
                    x = (i - (count - 1) / 2) * spacing
                    y = -layer * layer_spacing
                    pos[node] = (x, y)
    
            # 选择要查询的两个节点
            st.subheader("路径查询")
            node_list = list(G.nodes)
            unit1 = st.selectbox("选择起点单位", node_list)
            unit2 = st.selectbox("选择终点单位", node_list, index=min(1, len(node_list)-1))
    
            # 路径查询函数
            def check_relation(u1, u2):
                if nx.has_path(G, u1, u2):
                    return list(nx.all_simple_paths(G, source=u1, target=u2)), f"{u1} 比 {u2} 更早"
                elif nx.has_path(G, u2, u1):
                    return list(nx.all_simple_paths(G, source=u2, target=u1)), f"{u2} 比 {u1} 更早"
                else:
                    return [], f"{u1} 和 {u2} 之间无地层早晚关系"
    
            # 执行查询
            all_paths, relation_text = check_relation(unit1, unit2)
            st.markdown(f"**{relation_text}**")
    
            if all_paths:
                for path in all_paths:
                    st.markdown(" → ".join(path))
    
            # 提取高亮边
            highlight_edges = set()
            for path in all_paths:
                for i in range(len(path) - 1):
                    highlight_edges.add((path[i], path[i+1]))
                    
            # 提取所有高亮节点（路径中出现的节点）
            highlight_nodes = set()
            for path in all_paths:
                highlight_nodes.update(path)
            # 高亮用户查询的两个单位（即使无路径）
            highlight_nodes.update([unit1, unit2])
            
            # 画图
            # 计算图层和最大列数
            max_columns = max(len(v) for v in layers.values())
            num_layers = len(layers)
    
            # 根据横纵间距计算图尺寸（每层 1 spacing 高，每列 1 spacing 宽）
            fig_width = spacing * max_columns
            fig_height = layer_spacing * num_layers
    
            # 限制最大范围，防止超大图片
            fig_width = max(5, min(fig_width, 30))    # 宽度限制在 5 到 60 英寸
            fig_height = max(3, min(fig_height, 20))  # 高度限制在 3 到 40 英寸
    
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))        
            # 分别绘制普通节点和高亮节点
            default_edges = [e for e in G.edges if e not in highlight_edges]
            nx.draw_networkx_edges(G, pos, 
                                   edgelist=default_edges, 
                                   width=arrow_width, 
                                   edge_color='gray', 
                                   arrows=True, 
                                   arrowstyle='-|>',
                                   ax=ax)
            nx.draw_networkx_edges(G, pos, 
                                   edgelist=list(highlight_edges), 
                                   width=arrow_width + 1.5, 
                                   edge_color='red', arrows=True,
                                   arrowstyle='-|>',
                                   ax=ax)
    
    
            normal_nodes = [n for n in G.nodes if n not in highlight_nodes]
            nx.draw_networkx_nodes(G, pos,
                                nodelist=normal_nodes,
                                node_color='lightblue',
                                node_size=node_size,
                                ax=ax)
    
            nx.draw_networkx_nodes(G, pos,
                                nodelist=list(highlight_nodes),
                                node_color='orange',  # 可换成 red 或其他
                                node_size=node_size + 200,
                                ax=ax)
    
            nx.draw_networkx_labels(G, pos, font_size= font_size, font_family=font_name, ax=ax)
            ax.axis('off')
            st.pyplot(fig)
            
            # 保存图像到内存
            img_buffer = BytesIO()
            fig.savefig(img_buffer, format="png", dpi=300, bbox_inches='tight')
            img_buffer.seek(0)
            # 下载按钮
            st.download_button(
                label="📥下载为 PNG 图像",
                data=img_buffer,
                file_name="harris_matrix.png",
                mime="image/png"
            )
    except Exception as e:
        st.error(f"❌ 无法读取文件：{e}")    
