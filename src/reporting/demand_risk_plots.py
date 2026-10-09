"""Dez visualizações dos outputs da Fase 6; nenhuma leitura de raw ou refit."""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter,MaxNLocator
import numpy as np
import pandas as pd

from src.ingestion.source_manifest import ROOT
from src.reporting.demand_understanding_plots import finish,BLUE,ORANGE,GREEN
from src.segmentation.demand_risk import RISK_CELLS


CELL_LABELS={"NEITHER":"Nenhum dos dois","UNDERFORECAST_ONLY":"Só subprevisão persistente",
    "CENSORING_ONLY":"Só possível censura","CENSORING_AND_UNDERFORECAST":"Ambos os sinais"}
CELL_COLORS=[BLUE,ORANGE,GREEN,"#8F526D"]


def cdf(axis,values,label,color):
    values=np.sort(np.asarray(values.dropna()))
    axis.plot(values,np.arange(1,len(values)+1)/len(values),label=label,color=color)
    axis.yaxis.set_major_formatter(PercentFormatter(1))
    axis.set(ylabel="Fração acumulada das séries",ylim=(0,1))


def bias_distribution(data):
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for axis,metric in zip(axes,["bias","bias_pct"]):
        cdf(axis,data["uncertainty"][metric],metric,BLUE)
        axis.axvline(0,color="#65757f",ls="--",lw=1)
        axis.set_xscale("symlog",linthresh=.03)
        axis.set(xlabel=metric+" · escala simétrica log")
        if metric=="bias_pct":
            axis.xaxis.set_major_formatter(PercentFormatter(1))
    return finish(fig,"01 · Bias negativo não caracteriza sozinho persistência","28 dias agregados por série · sinal forecast − actual · não é estimativa de demanda perdida.")


def uncertainty_distribution(data):
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for metric,color in [("error_std",BLUE),("rmse",ORANGE)]:
        cdf(axes[0],data["uncertainty"][metric],metric,color)
    for metric,color in [("p90_absolute_error",GREEN),("p95_absolute_error","#8F526D")]:
        cdf(axes[1],data["uncertainty"][metric],metric,color)
    for axis in axes:
        axis.set(xscale="log",xlabel="Erro na escala normalizada · escala log")
        axis.legend()
    return finish(fig,"02 · Medidas complementares de dispersão e cauda","Desvio amostral, RMSE e quantis absolutos; nenhuma fórmula de safety stock escolhida. Apenas 28 observações por série.")


def persistence(data):
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    frame=data["persistence_distribution"]
    axes[0].bar(frame.negative_bias_fold_count,frame.n_series-frame.persistent_series,color=BLUE,label="Não cumpre regra completa")
    axes[0].bar(frame.negative_bias_fold_count,frame.persistent_series,bottom=frame.n_series-frame.persistent_series,color=ORANGE,label="Persistente")
    axes[0].set(xticks=range(5),xlabel="Folds com bias negativo",ylabel="Séries")
    axes[0].legend(fontsize=8)
    profile=data["risk_profile"]
    for flag,color,label in [(False,BLUE,"Não persistente"),(True,ORANGE,"Persistente")]:
        part=profile.loc[profile.persistent_underforecast_flag.eq(flag),"underforecast_rate"]
        axes[1].hist(part,bins=np.linspace(0,1,15),weights=np.ones(len(part))/len(part),alpha=.55,color=color,label=label)
    axes[1].set(xlabel="Fração de dias subprevistos",ylabel="Fração dentro do grupo")
    axes[1].xaxis.set_major_formatter(PercentFormatter(1)); axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].legend(fontsize=8)
    return finish(fig,"03 · Persistência exige sinal consolidado e ≥3 de 4 folds","16.529 séries persistentes · frequência diária e persistência do bias são medidas diferentes.")


def compare_groups(data,level,dimension,order,title,number):
    frame=data["calibration"].loc[data["calibration"].level.eq(level)].set_index(dimension).reindex(order)
    fig,axes=plt.subplots(2,3,figsize=(13,8))
    for axis,metric in zip(axes.flat,["mae","rmse","bias_pct","error_std","p95_absolute_error","underforecast_rate"]):
        bars=axis.bar([str(x) for x in order],frame[metric],color=[BLUE,ORANGE,GREEN][:len(order)])
        axis.set(title=metric)
        axis.axhline(0,color="#65757f",lw=.7)
        if metric in {"bias_pct","underforecast_rate"}:
            axis.yaxis.set_major_formatter(PercentFormatter(1))
        if metric=="underforecast_rate":
            axis.set_ylim(0,1)
    return finish(fig,f"{number:02d} · {title}","Classes conhecidas em 25/06; agrupamento descritivo dos erros passados. Associação não é causalidade.")


def stockout(data):
    return compare_groups(data,"stockout_exposure","stockout_exposure",["LOW","MEDIUM","HIGH"],"Maior exposição, maior dispersão e bias negativo",4)


def censoring(data):
    return compare_groups(data,"censoring_risk_flag","censoring_risk_flag",[False,True],"Flag de censura: magnitude maior, frequência semelhante",5)


def risk_matrix(data):
    frame=data["risk_matrix"].loc[data["risk_matrix"].level.eq("risk_cell")].set_index("demand_observation_risk_cell")
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    cells=np.array([["NEITHER","UNDERFORECAST_ONLY"],["CENSORING_ONLY","CENSORING_AND_UNDERFORECAST"]])
    for axis,metric,title in zip(axes,["n_series","train_normalized_sales_share"],["Número de séries","Participação na venda normalizada train"]):
        values=np.array([[frame.loc[cell,metric] for cell in row] for row in cells])
        axis.imshow(values,cmap="Blues",vmin=0,vmax=values.max()*1.3,aspect="auto")
        for i in range(2):
            for j in range(2):
                value=values[i,j]
                axis.text(j,i,f"{int(value):,}" if metric=="n_series" else f"{value:.2%}",ha="center",va="center",fontsize=16)
        axis.set(xticks=[0,1],xticklabels=["Não persistente","Persistente"],yticks=[0,1],yticklabels=["Flag=False","Flag=True"],title=title)
    return finish(fig,"06 · Dois sinais distintos, sem score ponderado","Duplo sinal: 1.028 séries e 1,98% da venda train. Nenhuma célula comprova demanda perdida.")


def risk_abc(data):
    frame=data["risk_matrix"].loc[data["risk_matrix"].level.eq("risk_abc")]
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for axis,metric,title in zip(axes,["n_series","train_normalized_sales_share"],["Séries por ABC","Participação na venda train total"]):
        bottom=np.zeros(3)
        for cell,color in zip(RISK_CELLS,CELL_COLORS):
            part=frame.loc[frame.demand_observation_risk_cell.eq(cell)].set_index("abc_class").reindex(list("ABC"))[metric].fillna(0)
            axis.bar(list("ABC"),part,bottom=bottom,label=CELL_LABELS[cell],color=color)
            bottom+=part.to_numpy()
        axis.set(title=title)
        if metric.endswith("share"):
            axis.yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(fontsize=8)
    return finish(fig,"07 · A/B com duplo sinal: prioridade de investigação","706 séries A + 258 B · 1,93% da venda train total · não constitui recomendação de compra.")


def xyz_uncertainty(data):
    frame=data["calibration"].loc[data["calibration"].level.eq("xyz")].set_index("xyz_class").reindex(list("XYZ"))
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for axis,measures in zip(axes,[["error_std","rmse"],["p90_absolute_error","p95_absolute_error"]]):
        for i,(metric,color) in enumerate(zip(measures,[BLUE,ORANGE])):
            axis.bar(np.arange(3)+(i-.5)*.36,frame[metric],width=.34,color=color,label=metric)
        axis.set(xticks=range(3),xticklabels=list("XYZ"),ylabel="Erro na escala normalizada")
        axis.legend()
    return finish(fig,"08 · XYZ e medidas de incerteza agregadas","Z apresenta maior dispersão e caudas neste agrupamento de 25/06. Quantis agrupados não são médias dos quantis por série.")


def examples(data):
    fig,axes=plt.subplots(4,2,figsize=(14,13))
    for axis,row in zip(axes.flat,data["example_selection"].itertuples()):
        f=data["example_forecasts"].loc[data["example_forecasts"].selection_rule.eq(row.selection_rule)]
        dates=pd.to_datetime(f.target_date)
        axis.plot(dates,f.actual,color="#34434c",label="Actual",marker=".",lw=1)
        axis.plot(dates,f.forecast,color=ORANGE,label="ETS preservado",lw=1.1)
        axis.fill_between(dates,f.forecast,f.actual,where=f.error.lt(0),color=ORANGE,alpha=.16,label="Subprevisão")
        for origin in ["2024-06-05","2024-06-12","2024-06-19"]:
            axis.axvline(pd.Timestamp(origin),color="#65757f",ls="--",lw=.5)
        axis.set(title=f"{row.selection_rule}\nloja {int(row.store_id)} · produto {int(row.product_id)} · D={row.actual_total:.2f}")
        axis.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.WE))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        axis.legend(fontsize=7,ncol=3)
    for axis in list(axes.flat)[len(data["example_selection"]):]:
        axis.axis("off")
    return finish(fig,"09 · Sete exemplos selecionados por regras reproduzíveis","Quatro folds já concluídos · exemplos explicam sinais; não validam risco futuro nem representam universalmente suas células.")


def robustness(data):
    frame=data["robustness"].loc[data["robustness"].scope.eq("global")].copy()
    labels={"official_all":"Oficial","central_98pct_error":"Erro p1–p99","exclude_low_actual_p05":"Sem baixa escala",
            **{f"omit_fold_{i}":f"Sem fold {i}" for i in range(1,5)}}
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for axis,metric in zip(axes,["rmse","bias_pct"]):
        axis.barh([labels[x] for x in frame.scenario],frame[metric],color=[BLUE]+[ORANGE]*(len(frame)-1))
        axis.axvline(0,color="#65757f",lw=.8)
        axis.set(title=metric)
        if metric=="bias_pct":
            axis.xaxis.set_major_formatter(PercentFormatter(1))
    return finish(fig,"10 · O bias global depende do fold 4; as caudas afetam RMSE","Sensibilidades descritivas apenas. Nenhuma exclusão altera os outputs oficiais; não equivalem a um novo modelo.")


PLOTS=[bias_distribution,uncertainty_distribution,persistence,stockout,censoring,risk_matrix,risk_abc,xyz_uncertainty,examples,robustness]


def save_figure(fig,number,root=ROOT):
    folder=root / "data/outputs/forecast_uncertainty/figures"
    folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder / f"{number:02d}_forecast_risk.png",dpi=145,bbox_inches="tight")
