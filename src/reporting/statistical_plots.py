"""Dez figuras comparativas; lê somente resultados salvos, sem ajustar modelos."""

import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter,MaxNLocator
import numpy as np
import pandas as pd

from src.ingestion.source_manifest import ROOT
from src.reporting.demand_understanding_plots import finish,BLUE,ORANGE,GREEN


MODELS=["seasonal_naive","ets_ana"]
LABELS={"seasonal_naive":"Seasonal Naive","ets_ana":"ETS A/N/A"}
COLORS={"seasonal_naive":BLUE,"ets_ana":ORANGE}


def load_outputs(root=ROOT):
    folder=root / "data/outputs/statistical_forecasting"
    summary=json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    data={"summary":summary,"metrics":pd.DataFrame(summary["metrics"]),"pairs":pd.DataFrame(summary["comparisons"])}
    for name in ["win_rates","materiality","fit_diagnostics","example_selection","example_forecasts","example_actuals"]:
        data[name]=pd.read_parquet(folder / f"{name}.parquet")
    data["series"]=pd.read_parquet(root / summary["artifacts"]["comparison"]["path"],filters=[("level","=","series")])
    return data


def grouped(axis,frame,dimension,order,metric,title):
    positions=np.arange(len(order))
    for index,model in enumerate(MODELS):
        values=frame.loc[frame.model.eq(model)].set_index(dimension).reindex(order)[metric]
        axis.bar(positions+(index-.5)*.36,values,width=.34,label=LABELS[model],color=COLORS[model])
    axis.set(xticks=positions,xticklabels=[str(x) for x in order],title=title)
    if metric in {"wape","bias_pct"}:
        axis.yaxis.set_major_formatter(PercentFormatter(1))
    if metric in {"bias","bias_pct"}:
        axis.axhline(0,color="#6b7880",lw=.8)
    axis.legend(fontsize=8)


def global_errors(data):
    frame=data["metrics"].loc[data["metrics"].level.eq("global")].set_index("model").reindex(MODELS)
    fig,axes=plt.subplots(1,3,figsize=(13,5))
    for axis,metric in zip(axes,["mae","rmse","wape"]):
        bars=axis.bar([LABELS[m] for m in MODELS],frame[metric],color=[COLORS[m] for m in MODELS],width=.55)
        axis.bar_label(bars,labels=[f"{v:.2%}" if metric=="wape" else f"{v:.4f}" for v in frame[metric]],padding=5)
        axis.set(title=metric.upper(),ylim=(0,frame[metric].max()*1.2))
        if metric=="wape":
            axis.yaxis.set_major_formatter(PercentFormatter(1))
    return finish(fig,"01 · Erros globais consolidados","1,4 milhão de previsões por modelo · mesmos actuals e denominadores · menor é melhor.")


def fold_errors(data):
    frame=data["metrics"].loc[data["metrics"].level.eq("fold")]
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for axis,metric in zip(axes,["wape","bias_pct"]):
        grouped(axis,frame,"fold_id",[1,2,3,4],metric,metric.upper())
    return finish(fig,"02 · Desempenho nas quatro origens","Horizonte de sete dias · origens 29/05, 05/06, 12/06 e 19/06/2024 · bias negativo = subprevisão.")


def class_errors(data,level,dimension,order,number):
    frame=data["metrics"].loc[data["metrics"].level.eq(level)]
    fig,axes=plt.subplots(1,3,figsize=(13,5))
    for axis,metric in zip(axes,["mae","wape","bias_pct"]):
        grouped(axis,frame,dimension,order,metric,metric.upper())
    return finish(fig,f"{number:02d} · Comparação por {level.upper()}","Classes conhecidas em cada origem; composição pode mudar entre folds. Escala altera a relação entre MAE e WAPE.")


def abc_errors(data):
    return class_errors(data,"abc","abc_class",["A","B","C"],3)


def xyz_errors(data):
    return class_errors(data,"xyz","xyz_class",["X","Y","Z"],4)


def matrix_improvement(data):
    frame=data["pairs"].loc[data["pairs"].level.eq("abc_xyz")]
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    bound=max(float(frame[["improvement_wape","improvement_rmse"]].abs().max().max()),.01)
    for axis,metric in zip(axes,["wape","rmse"]):
        values=frame.pivot(index="abc_class",columns="xyz_class",values=f"improvement_{metric}").reindex(index=list("ABC"),columns=list("XYZ"))
        plotted=axis.imshow(values,cmap="RdYlGn",vmin=-bound,vmax=bound,aspect="auto")
        for i in range(3):
            for j in range(3):
                axis.text(j,i,f"{values.iloc[i,j]:.1%}",ha="center",va="center",fontsize=12)
        axis.set(xticks=range(3),xticklabels=list("XYZ"),yticks=range(3),yticklabels=list("ABC"),title=metric.upper())
        fig.colorbar(plotted,ax=axis,format=PercentFormatter(1),shrink=.8)
    return finish(fig,"05 · Melhoria relativa em ABC × XYZ","(Seasonal Naive − ETS) / Seasonal Naive · positivo favorece ETS · grupos prospectivos.")


def availability(data):
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for row,(level,dimension,order) in enumerate([("stockout_exposure","stockout_exposure",["LOW","MEDIUM","HIGH"]),
                                                  ("censoring_risk_flag","censoring_risk_flag",[False,True])]):
        frame=data["metrics"].loc[data["metrics"].level.eq(level)]
        for axis,metric in zip(axes[row],["wape","bias_pct"]):
            grouped(axis,frame,dimension,order,metric,f"{dimension} · {metric.upper()}")
    return finish(fig,"06 · Disponibilidade e possível censura","Associações descritivas; nenhuma estimativa de demanda perdida ou correção das vendas observadas.")


def series_bias(data):
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for axis,metric in zip(axes,["bias","bias_pct"]):
        for suffix,model in [("seasonal_naive","seasonal_naive"),("ets","ets_ana")]:
            values=np.sort(data["series"][f"{metric}_{suffix}"].dropna())
            axis.plot(values,np.arange(1,len(values)+1)/len(values),color=COLORS[model],label=LABELS[model])
        axis.axvline(0,color="#617382",ls="--",lw=1)
        axis.set_xscale("symlog",linthresh=.03)
        axis.set(xlabel=metric+" · escala simétrica log",ylabel="Fração acumulada das séries",ylim=(0,1))
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.legend()
    return finish(fig,"07 · Distribuição do bias por série","28 dias agregados antes do bias · uma série, um peso · subprevisão não prova risco de ruptura.")


def wins_materiality(data):
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    wins=data["win_rates"].loc[data["win_rates"].metric.eq("wape")].copy()
    labels=["Global" if r.level=="global" else r.segment for r in wins.itertuples()]
    left=np.zeros(len(wins))
    for name,color,label in [("ets",ORANGE,"ETS"),("seasonal_naive",BLUE,"SN"),("tie","#bbc4ca","Empate")]:
        values=wins[f"{name}_rate"].to_numpy()
        axes[0].barh(labels,values,left=left,color=color,label=label)
        left+=values
    axes[0].set(title="Win rate por série · WAPE",xlim=(0,1))
    axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(ncol=3,fontsize=8)
    for metric,color in [("wape",ORANGE),("rmse",GREEN)]:
        values=np.sort(data["series"][f"improvement_{metric}"].dropna())
        axes[1].plot(values,np.arange(1,len(values)+1)/len(values),label=metric.upper(),color=color)
    axes[1].axvline(0,color="#617382",ls="--",lw=1)
    axes[1].set_xscale("symlog",linthresh=.1)
    axes[1].set(title="Distribuição da melhoria relativa",xlabel="Ganho positivo · escala simétrica log",ylabel="Fração acumulada",ylim=(0,1))
    axes[1].xaxis.set_major_formatter(PercentFormatter(1))
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].legend()
    return finish(fig,"08 · Ganho distribuído e materialidade","ABC/XYZ agregam só folds na respectiva classe; séries podem aparecer em mais de uma classe. Tabelas incluem MAE e limiares.")


def fit_diagnostics(data):
    frame=data["fit_diagnostics"].loc[data["fit_diagnostics"].level.eq("fold")].sort_values("fold_id")
    fig,axes=plt.subplots(1,3,figsize=(13,5))
    for axis,metric,title,color in zip(axes,["fallback_fits","clipped_forecasts","mean_clip_magnitude"],
                                      ["Ajustes com fallback","Previsões projetadas em zero","Magnitude média da projeção"],[BLUE,ORANGE,GREEN]):
        values=frame[metric].fillna(0)
        bars=axis.bar(frame.fold_id,values,color=color)
        axis.bar_label(bars,labels=[f"{v:.4f}" if metric=="mean_clip_magnitude" else f"{int(v)}" for v in values],padding=4)
        axis.set(title=title,xticks=[1,2,3,4],xlabel="Fold",ylim=(0,max(values.max()*1.25,1 if metric!="mean_clip_magnitude" else 1e-3)))
        if metric!="mean_clip_magnitude":
            axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    return finish(fig,"09 · Fallback e previsões negativas","Fallback é contado por ajuste; clipping por previsão. Valor original e razão continuam preservados no mart.")


def example_paths(data):
    examples=data["example_selection"]
    columns=2
    rows=(len(examples)+1)//columns
    fig,axes=plt.subplots(rows,columns,figsize=(14,3.5*rows),squeeze=False)
    for axis,row in zip(axes.flat,examples.itertuples()):
        actual=data["example_actuals"].loc[data["example_actuals"].selection_rule.eq(row.selection_rule)]
        forecasts=data["example_forecasts"].loc[data["example_forecasts"].selection_rule.eq(row.selection_rule)]
        axis.plot(pd.to_datetime(actual.dt),actual.sale_amount,color="#333e49",label="Actual train",marker=".",lw=1)
        for model in MODELS:
            part=forecasts.loc[forecasts.model.eq(model)]
            axis.plot(pd.to_datetime(part.target_date),part.forecast,color=COLORS[model],label=LABELS[model],marker="o",ms=3)
            if model=="ets_ana" and part.negative_clipped.fillna(False).any():
                axis.scatter(pd.to_datetime(part.target_date),part.forecast_unclipped,color=ORANGE,marker="x",label="ETS sem clipping")
        axis.axvline(pd.Timestamp(row.forecast_origin),color="#617382",ls="--",lw=.8)
        axis.set(title=f"{row.selection_rule}\nloja {int(row.store_id)} · produto {int(row.product_id)} · D={row.actual_sum:.3f}")
        axis.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        axis.legend(fontsize=7,ncol=3)
    for axis in list(axes.flat)[len(examples):]:
        axis.axis("off")
    return finish(fig,"10 · Exemplos escolhidos por regras explícitas","Extremos descritivos, sem uso na seleção de modelo. Sem exemplo populacional de fallback quando sua contagem é zero.")


PLOTS=[global_errors,fold_errors,abc_errors,xyz_errors,matrix_improvement,availability,series_bias,wins_materiality,fit_diagnostics,example_paths]


def save_figure(fig,number,root=ROOT):
    folder=root / "data/outputs/statistical_forecasting/figures"
    folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder / f"{number:02d}_statistical_forecasting.png",dpi=145,bbox_inches="tight")
