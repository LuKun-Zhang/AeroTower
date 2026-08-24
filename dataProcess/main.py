import json
import time
import sys
# import matplotlib.pyplot as plt

use_static = False

files = ["./sichuan_big_graph/A320_C8Y156_big.json", "./sichuan_big_graph/A319_C8Y124_big.json"]

def getinput(file_path):
    with open(file_path, 'r') as load_f:
        data = json.load(load_f)

    nodes = data['nodes']
    edges = data['edges']

    node2id = {}
    id2node = {}
    node2in = {}
    node2out = {}
    node2diff = {}

    node_num = 0
    for k, v in nodes.items():
        node_num += 1
        node2id[k] = node_num
        id2node[node_num] = k
        if use_static:
            node2in[k] = 0
            node2out[k] = 0
            node2diff[k] = 0

    Graph = [[False for _ in range(node_num)] for _ in range(node_num)]



    formated_edges = []
    for k, v in edges.items():
        formated_edges.append((node2id[str(v['from'])], node2id[str(v['to'])]))
        Graph[node2id[str(v['from'])]-1][node2id[str(v['to'])]-1] = True
        if use_static:
            node2in[str(v['to'])] += 1
            node2out[str(v['from'])] += 1
            node2diff[str(v['to'])] += 1
            node2diff[str(v['from'])] -= 1

    return Graph, node2id, id2node, node2in, node2out, node2diff

def judgeDAG(Graph):
    node_num = len(Graph)
    visited = [False] * node_num
    in_path = []
    has_loop = False

    def dfs(x):
        global has_loop
        in_path.append(x)
        visited[x] = True
        for y in range(node_num):
            if Graph[x][y] and y in in_path:
                has_loop = True
                print("Loop detected!")
                path_index = in_path.index(y)
                print("->".join(in_path[path_index:]), "->", y)
            if not visited[y] and Graph[x][y]:
                dfs(y)
        in_path.remove(x)
        
    for i in range(node_num):
        if not visited[i]:
            dfs(i)

    if not has_loop:
        print("No Loop detected, Graph is DAG")

def outputPath(Graph, pre_matched, post_matched, id2node, output_file):
    visited = [False] * node_num
    paths = []
    for i in range(node_num):
        path_node_list = []
        path_node_list_str = [] 
        if not visited[i]:
            x = i
            while x is not -1:
                visited[x] = True
                path_node_list.append(x)
                path_node_list_str.append(id2node[x+1])
                x = pre_matched[x]
            path_node_list.reverse()
            path_node_list_str.reverse()
            x = i
            while post_matched[x] is not -1:
                x = post_matched[x]
                visited[x] = True
                path_node_list.append(x)
                path_node_list_str.append(id2node[x+1])
            # print(" -> ".join(path_node_list_str))
            paths.append(path_node_list_str)
    with open(output_file, "w") as f: 
        json.dump(paths, f)

def bipartMatching(Graph):
    matched_num = 0
    node_num = len(Graph)
    visited = [False for _ in range(node_num)]
    pre_matched = [-1 for _ in range(node_num)]
    post_matched = [-1 for _ in range(node_num)]

    def dfs(x):
        for y in range(node_num):
            if y == x: continue
            if Graph[x][y] and not visited[y]:
                visited[y] = True
                if pre_matched[y] == -1:
                    pre_matched[y] = x
                    post_matched[x] = y
                    return True
                elif dfs(pre_matched[y]):
                    pre_matched[y] = x
                    post_matched[x] = y
                    return True
        return False

    for x in range(node_num):
        visited = [False for _ in range(node_num)]
        if dfs(x):
            matched_num += 1
    return matched_num, pre_matched, post_matched

def static(node2in, node2out, node2diff):
    pass
    # ins, outs, diffs = {}, {}, {}
    # for k, v in node2in.items():
    #     ins[v] = ins.get(v, 0) + 1
    # for k, v in node2out.items():
    #     outs[v] = outs.get(v, 0) + 1
    # for k, v in node2diff.items():
    #     diffs[v] = diffs.get(v, 0) + 1
    # print(ins)
    # print(outs)
    # print(diffs)
    # maxin = max(ins.keys())
    # inlist = [0] * (maxin + 1)
    # for i in range(maxin + 1):
    #     inlist[i] = ins.get(i, 0)
    # plt.bar(range(maxin + 1), inlist)
    # # plt.xticks(maxin + 1, range(maxin+1))
    # plt.xlabel("In Degree")
    # plt.ylabel("Node number")
    # plt.text(15, 100, "Total node number is {}".format(len(node2in.keys())))
    # plt.text(15 ,80, "Total node degree is {}".format(sum(node2in.values())))
    # plt.show() 
    # maxout = max(outs.keys())
    # outlist = [0] * (maxout + 1)
    # for i in range(maxout + 1):
    #     outlist[i] = outs.get(i, 0)
    # plt.bar(range(maxout + 1), outlist)
    # # plt.xticks(maxout + 1, range(maxout+1))
    # plt.xlabel("Out Degree")
    # plt.ylabel("Node number")
    # plt.text(15, 100, "Total node number is {}".format(len(node2out.keys())))
    # plt.text(15 ,80, "Total node degree is {}".format(sum(node2out.values())))
    # plt.show() 
    # maxdiff = max(diffs.keys())
    # mindiff = min(diffs.keys())
    # difflist = [0] * (maxdiff + 1 - mindiff)
    # for i in range(mindiff, maxdiff + 1):
    #     difflist[i-mindiff] = diffs.get(i, 0)
    # plt.bar(range(mindiff, maxdiff + 1), difflist)
    # # plt.xticks(maxdiff + 1, range(maxdiff+1))
    # plt.xlabel("Degree diff(In degree - Out degree)")
    # plt.ylabel("Node number")
    # plt.text(10, 30, "Total node number is {}".format(len(node2diff.keys())))
    # plt.text(10 ,20, "Total node degree is {}".format(sum(node2diff.values())))
    # plt.show() 
    # D = ins
    # plt.bar(range(len(D)), list(D.values()), align='center')
    # plt.xticks(range(len(D)), list(D.keys()))
    # plt.xlabel("In Degree")
    # plt.ylabel("Node number")
    # plt.show()


if __name__ == "__main__":
    input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        output_file = "output.json" 
    # print(sys.argv[1])
    Graph, node2id, id2node, node2in, node2out, node2diff = getinput(input_file)

    node_num = len(Graph)
    judgeDAG(Graph)
    s = time.time()
    matched_num ,pre_matched, post_matched = bipartMatching(Graph)
    e = time.time()
    print("Path number to cover: {}".format(len(Graph) - matched_num))
    outputPath(Graph, pre_matched, post_matched, id2node, output_file)
    # print("")
    if use_static:
        static(node2in, node2out, node2diff)
    print("Path result outputed to {}".format(output_file))
    print("Used time: {}".format(e - s))
