#!/usr/bin/env python

import sys
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from log_parser import *

palette = ["#aaeeff", "#11bbff", "#0077aa"]

renaming = {
"ProductionModel.1LUT_B_128_D_64_E1_10000000_L1_50": "1LUT",
"ProductionModel.2LUT_B_128_D_64_E1_10000000_E2_10000000_L1_50_L2_50": "2LUT",
"ProductionModel.C3_B_128_WX_1000_WY_1024": "C3",
"ProductionModel.MLP1_B_128_M_2000_N_128": "MLP1",
"ProductionModel.MLP3_B_128_N_128_O_64_P_32_Q_2": "MLP3",
"BatchMatMul.TransposedBatchMatMul_B_500_K_26_M_72_N_26": "tbmm (Fact.Machines)",
"GroupConvolution.GroupConvolution_C_4_F_4_G_32_H_56_KH_3_KW_3_N_32_W_56": "gconv (ResNeXt-2)",
"GroupConvolution.GroupConvolution_C_8_F_8_G_32_H_28_KH_3_KW_3_N_32_W_28": "gconv (ResNeXt-3)",
"GroupConvolution.GroupConvolution_C_16_F_16_G_32_H_14_KH_3_KW_3_N_32_W_14": "gconv (ResNeXt-4)",
"GroupConvolution.GroupConvolution_C_32_F_32_G_32_H_7_KH_3_KW_3_N_32_W_7": "gconv (ResNeXt-5)",
"GroupNormalization.GroupNormalization_C_512_G_32_H_12_N_4_W_12": "GroupNorm (batch=4)",
"GroupNormalization.GroupNormalization_C_512_G_32_H_48_N_32_W_48": "GroupNorm (batch=32)",
"Kronecker.Kronecker3_D0_16_D1_16_D2_16_M_256_N0_32_N1_32_N2_32": "KRU small",
"Kronecker.Kronecker3_D0_16_D1_16_D2_16_M_256_N0_64_N1_64_N2_64": "KRU medium",
"Kronecker.Kronecker3_D0_16_D1_16_D2_16_M_256_N0_64_N1_128_N2_128": "KRU large",
"TransposedMatMul.TransposedMatMul_K_32_M_128_N_256": "tmm small",
"TransposedMatMul.TransposedMatMul_K_1024_M_128_N_1024": "tmm medium",
"TransposedMatMul.TransposedMatMul_K_4096_M_128_N_16384": "tmm large"
}

def filter_out(benchmarks):
    skip_names = ["Moments", "WaveNet", "Kronecker", "C3"]
    result = []
    for b in benchmarks:
        skip = False
        for s in skip_names:
            if s in b.name:
                skip = True
        if "GroupNormalizationSingleKernel" in b.name:
            skip = True
        if skip:
            continue
        result.append(b)
    return result

def zip_archs(benchmarks_p, benchmarks_v):
    result = []
    for bp in benchmarks_p:
        for bv in benchmarks_v:
            if bp.name != bv.name or bp.params != bv.params:
                continue
            result.append((bp, bv))
    return result

def append_graph_values(names, median_speedups, bottoms, heights, color, b, baseline, tc):
    names.append(b.name + "_" + b._Benchmark__textualize_params())
    median_speedups.append(float(baseline) / tc if baseline is not None and tc is not None else None)
    if median_speedups[-1] is None:
        bottoms.append(1)
        heights.append(0)
        color.append("black")
    elif median_speedups[-1] < 1:
        bottoms.append(median_speedups[-1])
        heights.append(1 - median_speedups[-1])
        color.append(palette[1])
    else:
        bottoms.append(1)
        heights.append(median_speedups[-1] - 1)
        color.append(palette[2])

def legend_3x():
    p0 = mpatches.Patch(facecolor=palette[0], edgecolor="black", label='TC on P100')
    p1 = mpatches.Patch(facecolor=palette[1], edgecolor="black", label='TC on V100')
    p2 = mpatches.Patch(facecolor=palette[2], edgecolor="black", label='Caffe2 on V100')
    plt.legend(handles=[p0, p1, p2])

def legend_none():
    pass

def plot_barchart(names, xticks, width, posx, median_speedups, bottoms, heights, color, filename, ylabel, legend = legend_none):
    markers_x = []
    markers_y = []
    for i, m in enumerate(median_speedups):
        if m == None:
            markers_x.append(i * width)
            markers_y.append(1)

    yticks = [0.1, 0.2, 0.5, 1, 2, 4, 8]

    plt.clf()
    plt.figure(figsize=(7,4))
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.size"] = 10
    plt.ylim(0.1,10)
    plt.yscale("log")
    plt.grid(color="lightgray", alpha=0.5, zorder=-10)
    plt.yticks(yticks, map(str, yticks), family='serif')
    plt.ylabel(ylabel, family='serif')
    plt.xticks(xticks, map(lambda x: renaming[x], names), rotation=20, ha="right", va="top", family='serif')
    plt.bar(posx, heights, width, bottoms, label="Speedups", color=color, edgecolor="black", zorder=10)
    plt.scatter(markers_x, markers_y, marker='x')
    plt.axhline(1, color="black")
    legend()
    plt.tight_layout()
    plt.savefig(filename + ".pdf", format="pdf", bbox_inches="tight")

def plot_3x_speedups(names, median_speedups, bottoms, heights, color, filename, ylabel):
    width = 1. / 4 / len(names)
    names = [names[i] for i in xrange(0, len(names), 3)]
    xticks = [x * 4 * width + 1.5 * width for x in range(len(names))]
    posx = []
    for i in range(len(names)):
        posx += [4*width*i + width/2 + k*width for k in range(3)]
    plot_barchart(names, xticks, width, posx, median_speedups, bottoms, heights, color, filename, ylabel, legend_3x)

def plot_speedups(names, median_speedups, bottoms, heights, color, filename, ylabel):
    print "-------------------------------------------------------"
    print "Plotting", ylabel, "to", filename
    for (n, s) in zip(names, median_speedups):
        print n, " = ", s

    width = 1. / len(names)
    xticks = [x * width for x in range(len(names))]
    posx = [x * width for x in range(len(median_speedups))]
    plot_barchart(names, xticks, width, posx, median_speedups, bottoms, heights, color, filename, ylabel)
        
def plot_cross_benchmarks(benchmarks_p, benchmarks_v, kind, filename, ylabel):
    benchmarks_p = filter_out(aggregate_kronecker(benchmarks_p))
    benchmarks_v = filter_out(aggregate_kronecker(benchmarks_v))
    pairs = zip_archs(benchmarks_p, benchmarks_v)

    names = []
    median_speedups = []
    bottoms = []
    heights = []
    color = []
    for p in pairs:
        baseline = p[0].c2["p50"]
        tc = p[1][kind]["p50"]
        append_graph_values(names, median_speedups, bottoms, heights, color, p[0], baseline, tc)

    plot_speedups(names, median_speedups, bottoms, heights, color, filename, ylabel)

def plot_benchmarks(benchmarks, filename, ylabel):
    benchmarks = filter_out(aggregate_kronecker(benchmarks))

    names = []
    median_speedups = []
    bottoms = []
    heights = []
    color = []
    for b in benchmarks:
        caffe2 = b.c2["p50"]
        tc = b.tc["p50"]
        append_graph_values(names, median_speedups, bottoms, heights, color, b, caffe2, tc)
    
    plot_speedups(names, median_speedups, bottoms, heights, color, filename, ylabel)

order = [
"TransposedMatMul.TransposedMatMul_K_32_M_128_N_256",
"TransposedMatMul.TransposedMatMul_K_1024_M_128_N_1024",
"TransposedMatMul.TransposedMatMul_K_4096_M_128_N_16384",
"GroupConvolution.GroupConvolution_C_4_F_4_G_32_H_56_KH_3_KW_3_N_32_W_56",
"GroupConvolution.GroupConvolution_C_8_F_8_G_32_H_28_KH_3_KW_3_N_32_W_28",
"GroupConvolution.GroupConvolution_C_16_F_16_G_32_H_14_KH_3_KW_3_N_32_W_14",
"GroupConvolution.GroupConvolution_C_32_F_32_G_32_H_7_KH_3_KW_3_N_32_W_7",
"GroupNormalization.GroupNormalization_C_512_G_32_H_12_N_4_W_12",
"GroupNormalization.GroupNormalization_C_512_G_32_H_48_N_32_W_48",
"ProductionModel.1LUT_B_128_D_64_E1_10000000_L1_50",
"ProductionModel.2LUT_B_128_D_64_E1_10000000_E2_10000000_L1_50_L2_50",
"ProductionModel.MLP1_B_128_M_2000_N_128",
"ProductionModel.MLP3_B_128_N_128_O_64_P_32_Q_2",
"BatchMatMul.TransposedBatchMatMul_B_500_K_26_M_72_N_26",
]

def plot_3x_benchmarks(benchmarks_p, benchmarks_v, filename, ylabel):
    benchmarks_p = filter_out(aggregate_kronecker(benchmarks_p))
    benchmarks_v = filter_out(aggregate_kronecker(benchmarks_v))

    global order
    benchmarks_p = sorted(benchmarks_p, key = lambda b: order.index(b.name + "_" + b._Benchmark__textualize_params()))
    benchmarks_v = sorted(benchmarks_v, key = lambda b: order.index(b.name + "_" + b._Benchmark__textualize_params()))

    pairs = zip_archs(benchmarks_p, benchmarks_v)

    names = []
    median_speedups = []
    bottoms = []
    heights = []
    color = []
    for p in pairs:
        c2_p100 = p[0].c2["p50"]
        c2_v100 = p[1].c2["p50"]
        tc_v100 = p[1].tc["p50"]
	tc_p100 = p[0].tc["p50"]
        append_graph_values(names, median_speedups, bottoms, heights, color, p[0], c2_p100, tc_p100)
        color[-1] = palette[0]
        append_graph_values(names, median_speedups, bottoms, heights, color, p[0], c2_p100, tc_v100)
        color[-1] = palette[1]
        append_graph_values(names, median_speedups, bottoms, heights, color, p[0], c2_p100, c2_v100)
        color[-1] = palette[2]

    plot_3x_speedups(names, median_speedups, bottoms, heights, color, filename, ylabel)



if __name__ == "__main__":
    with open("P100.txt") as f:
        lines = f.readlines()
        p100 = parse_one_log(lines)

    with open("V100.txt") as f:
        lines = f.readlines()
        v100 = parse_one_log(lines)

    plot_benchmarks(p100, "tc_p100_caffe2_p100", "Speedup over Caffe2 (log scale)")
    plot_benchmarks(v100, "tc_v100_caffe2_v100", "Speedup over Caffe2 (log scale)")
    plot_cross_benchmarks(p100, v100, "Caffe2", "caffe2_p100_caffe2_v100", "Speedup over P100 (log scale)")
    plot_cross_benchmarks(p100, v100, "autotuned", "tc_v100_caffe2_p100", "Speedup over Caffe2 on P100 (log scale)")
    plot_3x_benchmarks(p100, v100, "v100_all", "Speedup over Caffe2 on P100 (log scale)")


