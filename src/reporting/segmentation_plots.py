"""Nove figuras da Fase 3, consumindo somente artefatos reproduzíveis."""

import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from src.ingestion.source_manifest import ROOT
from src.reporting.demand_understanding_plots import finish,BLUE,GREEN,ORANGE


CLASS_COLORS={"X":GREEN,"Y":BLUE,"Z":ORANGE}
EXPOSURE_COLORS={"LOW":"#9dcbbd","MEDIUM":BLUE,"HIGH":ORANGE}


def load_outputs(root=ROOT):
    summary=json.loads((root / "data/outputs/segmentation/summary.json").read_text(encoding="utf-8"))
    return {"summary":summary,**{name:pd.read_parquet(root / entry["path"]) for name,entry in summary["artifacts"].items()}}


def abc_curve(data):
    abc=data["product_abc"]
    counts=pd.DataFrame(data["summary"]["abc"]["distribution"])
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    axes[0].plot(abc.abc_rank,abc.normalized_sales_cumulative_share,color=BLUE,lw=2)
    for limit,color in [(.8,ORANGE),(.95,GREEN)]:
        first=abc.loc[abc.normalized_sales_cumulative_share>=limit].iloc[0]
        axes[0].axhline(limit,color=color,ls="--",lw=1)
        axes[0].axvline(first.abc_rank,color=color,ls=":",lw=1)
        axes[0].annotate(f"{int(first.abc_rank)} produtos → {limit:.0%}",
                         (first.abc_rank,limit),xytext=(12,-30 if limit==.8 else -18),textcoords="offset points",fontsize=9)
    axes[0].set(xlabel="Produtos ordenados por contribuição",ylabel="Venda normalizada acumulada",ylim=(0,1.02))
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    bars=axes[1].bar(counts.abc_class,counts.n_products,color=[BLUE,GREEN,ORANGE])
    axes[1].bar_label(bars,padding=3)
    axes[1].set(ylabel="Número de produtos",xlabel="ABC do produto",ylim=(0,counts.n_products.max()*1.14))
    return finish(fig,"01 · ABC por produto concentra relevância, sem valor financeiro",
                  "O produto que cruza 80%/95% encerra a classe · classe global propagada às séries loja-produto.")


def correlations(data):
    rows=data["correlations"]
    metrics=["coefficient_of_variation","weekly_coefficient_of_variation","weekly_pattern_half_correlation",
             "weekly_pattern_half_mae","autocorrelation_lag7","zero_ratio","adi"]
    labels=["CV dia","CV semana","Corr. forma","MAE forma","Lag 7","Zeros","ADI"]
    fig,axes=plt.subplots(1,2,figsize=(13,5.8))
    for axis,method in zip(axes,["pearson","spearman"]):
        matrix=rows.loc[rows.method==method].pivot(index="metric_1",columns="metric_2",values="correlation").loc[metrics,metrics]
        image=axis.imshow(matrix,vmin=-1,vmax=1,cmap="RdBu_r")
        for i in range(7):
            for j in range(7):
                value=matrix.iloc[i,j]
                axis.text(j,i,f"{value:.2f}",ha="center",va="center",fontsize=8,color="white" if abs(value)>.65 else "#173447")
        axis.set(xticks=range(7),yticks=range(7),xticklabels=labels,yticklabels=labels,title=method.title())
        axis.tick_params(axis="x",rotation=40)
        axis.figure.colorbar(image,ax=axis,fraction=.035,pad=.025)
    return finish(fig,"02 · Dois eixos complementares evitam duplicar o mesmo sinal",
                  "Pares válidos · CV diário/semanal são associados; CV semanal/correlação de forma têm associação fraca.")


def xyz_rules(data):
    frame=data["series_xyz"]
    t=data["summary"]["xyz"]["thresholds"]
    fig,axis=plt.subplots(figsize=(11,5.8))
    for cls in ["Z","Y","X"]:
        rows=frame.loc[frame.xyz_class==cls].dropna(subset=["weekly_pattern_half_correlation"])
        axis.scatter(rows.weekly_coefficient_of_variation,rows.weekly_pattern_half_correlation,
                     s=3,alpha=.25,color=CLASS_COLORS[cls],rasterized=True,label=cls)
    for value in [t["variability_low"],t["variability_high"]]:
        axis.axvline(value,color="#354c5a",lw=1,ls="--")
    for value in [t["stability_low"],t["stability_good"]]:
        axis.axhline(value,color="#354c5a",lw=1,ls="--")
    axis.set(xlabel="CV semanal",ylabel="Correlação da forma entre metades",ylim=(-1.03,1.03))
    axis.legend(title="XYZ",markerscale=4,loc="upper right")
    return finish(fig,"03 · XYZ usa duas regras explícitas, sem pesos ou clustering",
                  "Todos os pares válidos · 4 séries sem correlação ficam em Z pelo CV alto e não aparecem neste plano.")


def class_diagnostics(data):
    fig,axes=plt.subplots(2,2,figsize=(12,7.2))
    metrics=[("coefficient_of_variation","CV diário"),("weekly_coefficient_of_variation","CV semanal"),
             ("weekly_pattern_half_correlation","Correlação da forma"),("autocorrelation_lag7","Correlação lag 7 (diagnóstico)")]
    for axis,(metric,label) in zip(axes.flat,metrics):
        stats=data["xyz_class_profiles"].loc[lambda d:d.metric==metric].set_index("xyz_class").loc[["X","Y","Z"]]
        for i,cls in enumerate(["X","Y","Z"]):
            row=stats.loc[cls]
            axis.errorbar(i,row["median"],yerr=[[row["median"]-row.p25],[row.p75-row["median"]]],
                          fmt="o",markersize=7,capsize=8,color=CLASS_COLORS[cls],elinewidth=3)
        axis.set(xticks=[0,1,2],xticklabels=["X","Y","Z"],ylabel=label,xlim=(-.5,2.5))
    return finish(fig,"04 · Classes diferem nos eixos escolhidos; lag 7 não segue a ordem",
                  "Ponto = mediana; intervalo = p25–p75 das séries · separação descritiva, não validação de desempenho preditivo.")


def xyz_sizes(data):
    s=data["summary"]
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    counts=s["xyz"]["distribution"]
    bars=axes[0].bar(list(counts),list(counts.values()),color=list(CLASS_COLORS.values()))
    axes[0].bar_label(bars,padding=3)
    axes[0].set(ylabel="Séries",xlabel="Regra escolhida",ylim=(0,max(counts.values())*1.15))
    candidates=s["xyz"]["candidates"]
    bottom=np.zeros(len(candidates))
    x=np.arange(len(candidates))
    for cls in ["X","Y","Z"]:
        values=np.array([row["class_counts"][cls]/s["n_series"] for row in candidates])
        axes[1].bar(x,values,bottom=bottom,label=cls,color=CLASS_COLORS[cls])
        bottom+=values
    axes[1].set(xticks=x,xticklabels=["Semanal\nquartis","Semanal\nmediana/caudas","Semanal\ntercis","Diário\nmediana/caudas"],ylabel="Parcela das séries",ylim=(0,1.15))
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].legend(ncols=3,loc="upper center",frameon=False)
    return finish(fig,"05 · A escolha dos quantis importa; classes não têm cotas iguais",
                  "Comparação de regras exclusivamente em train · nenhuma seleção por erro de previsão.")


def stockout_exposure(data):
    s=data["summary"]
    t=s["exposure"]["thresholds"]
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    axes[0].hist(data["stockout_exposure"].stockout_rate,bins=30,color=BLUE)
    for value,label in [(t["stockout_low"],"p25"),(t["stockout_high"],"p75")]:
        axes[0].axvline(value,color=ORANGE,ls="--",label=f"{label}: {value:.2%}")
    axes[0].set(xlabel="Frequência de ruptura por série [06h,22h)",ylabel="Séries")
    axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend()
    distribution=pd.DataFrame(s["exposure"]["distribution"]).set_index("stockout_exposure").loc[["LOW","MEDIUM","HIGH"]]
    bars=axes[1].bar(distribution.index,distribution.n_series,color=list(EXPOSURE_COLORS.values()))
    axes[1].bar_label(bars,padding=3)
    axes[1].set(ylabel="Séries",xlabel="Exposição relativa",ylim=(0,distribution.n_series.max()*1.15))
    return finish(fig,"06 · Ruptura é uma dimensão separada da estabilidade",
                  "LOW não significa ausência de ruptura · HIGH indica frequência relativa, não severidade total nem causalidade.")


def abc_xyz_matrix(data):
    fig,axes=plt.subplots(1,2,figsize=(11,5.2))
    for axis,metric,title in zip(axes,["n_series","normalized_sales_share"],["Número de séries","Participação na venda normalizada"]):
        matrix=data["abc_xyz_matrix"].pivot(index="abc_class",columns="xyz_class",values=metric).loc[["A","B","C"],["X","Y","Z"]]
        axis.imshow(matrix,cmap="Blues",vmin=0)
        for i in range(3):
            for j in range(3):
                value=matrix.iloc[i,j]
                text=f"{int(value):,}" if metric=="n_series" else f"{value:.2%}"
                axis.text(j,i,text,ha="center",va="center",fontsize=13,color="white" if value>matrix.to_numpy().max()*.5 else "#173447")
        axis.set(xticks=range(3),xticklabels=["X","Y","Z"],yticks=range(3),yticklabels=["A","B","C"],
                 xlabel="XYZ da série",ylabel="ABC do produto",title=title)
    return finish(fig,"07 · Relevância global e estabilidade local formam nove perfis",
                  "Venda observada normalizada · produtos podem aparecer em várias colunas XYZ; séries não se repetem.")


def abc_xyz_availability(data):
    cube=data["exposure_cube"].copy()
    cube["cell"]=cube.abc_class+cube.xyz_class
    cells=[a+x for a in "ABC" for x in "XYZ"]
    pivot=cube.pivot(index="cell",columns="stockout_exposure",values="n_series").reindex(cells).fillna(0)
    fractions=pivot.div(pivot.sum(axis=1),axis=0)
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    bottom=np.zeros(9)
    for label,color in EXPOSURE_COLORS.items():
        values=fractions[label].to_numpy()
        axes[0].bar(cells,values,bottom=bottom,color=color,label=label)
        bottom+=values
    axes[0].set(ylabel="Parcela das séries da célula",xlabel="ABC × XYZ",ylim=(0,1.16))
    axes[0].legend(ncols=3,loc="upper center",frameon=False,fontsize=9)
    matrix=data["abc_xyz_matrix"]
    axes[1].bar(matrix.abc_class+matrix.xyz_class,matrix.censoring_risk_share,color=ORANGE)
    axes[1].set(ylabel="Parcela com flag de possível censura",xlabel="ABC × XYZ")
    for axis in axes:
        axis.yaxis.set_major_formatter(PercentFormatter(1))
    return finish(fig,"08 · Exposição e possível censura mudam a leitura da matriz",
                  "Flag = ruptura ≥ p75 e zeros ≥ p75 · não estima vendas perdidas; ausência da flag não elimina censura.")


def examples(data):
    fig,axes=plt.subplots(3,2,figsize=(14,10),sharex=True)
    labels={"AX_MAX_SALES":"AX · maior venda","AX_MAX_STOCKOUT":"AX · maior ruptura",
            "AZ_MAX_STOCKOUT":"AZ · maior ruptura","A_CENSOR_HIGH_STOCKOUT":"A + flag · maior ruptura",
            "CX_MEDIAN_WEEKLY_CV":"CX · próximo à mediana de CV semanal","CZ_MEDIAN_WEEKLY_CV":"CZ · próximo à mediana de CV semanal"}
    for axis,row in zip(axes.flat,data["summary"]["examples"]):
        values=data["example_series"].loc[lambda f:f.selection_rule==row["selection_rule"]].sort_values("dt")
        axis.plot(values.dt,values.sale_amount,color=BLUE,lw=1.2)
        affected=values.stock_hour6_22_cnt>0
        axis.scatter(values.loc[affected,"dt"],values.loc[affected,"sale_amount"],color=ORANGE,s=10)
        axis.set_title(f"{labels[row['selection_rule']]}\nLoja {row['store_id']} / produto {row['product_id']} · {row['stockout_exposure']} · flag {row['censoring_risk_flag']}",fontsize=9,loc="left")
        axis.set_ylabel("Venda normalizada")
        axis.set_ylim(bottom=0)
        axis.xaxis.set_major_locator(mdates.MonthLocator())
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    return finish(fig,"09 · Exemplos por regra tornam as classificações inspecionáveis",
                  "Pontos laranja = dias com ruptura · escalas próprias · proximidade à mediana refere-se somente ao CV semanal.")


PLOTS=[abc_curve,correlations,xyz_rules,class_diagnostics,xyz_sizes,stockout_exposure,abc_xyz_matrix,abc_xyz_availability,examples]


def save_figure(fig,number,root=ROOT):
    folder=root / "data/outputs/segmentation/figures"
    folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder / f"{number:02d}.png",dpi=140,facecolor="white")
