"""Notebook final: dez figuras a partir dos outputs, sem refit nem raw."""

import os
from pathlib import Path
import sys
from time import perf_counter

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from src.forecasting.statistical_backtesting import write_json
    from src.forecasting.holdout import FOLDER,read_json
    started=perf_counter()
    runtime=ROOT/".tmp/jupyter_runtime"
    runtime.mkdir(parents=True,exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"]=str(runtime)
    os.environ["IPYTHONDIR"]=str(ROOT/".ipython")
    os.environ["MPLCONFIGDIR"]=str(ROOT/".matplotlib")
    topics=[("Comparação global","Mesmos 350.000 actuals por modelo. Improvement usa Seasonal Naive como denominador; bias é assinado."),
        ("WAPE e consistência temporal","Quatro folds são referência descritiva, não intervalo de confiança."),
        ("Bias temporal","Não existe limite prévio de aceitabilidade operacional; não inventar um após abrir eval."),
        ("ABC","Classes congeladas em 25/06; venda observada normalizada não é receita."),
        ("XYZ","Classes conhecidas antes da origem; nenhuma recalibração no holdout."),
        ("Persistência prospectiva","Bias histórico negativo e pelo menos três folds negativos: 16.529 séries fixas."),
        ("Matriz de risco","Sinais pré-holdout, sem score; não inferir causalidade ou demanda perdida."),
        ("A e duplo sinal","As mesmas 706 séries identificadas antes da abertura; sem seleção pelo resultado."),
        ("Incerteza histórica","Quartis congelados; associação com erro futuro pode refletir escala e dependência entre séries."),
        ("Exemplos anteriores","Sete regras da Fase 6, sem cherry-picking no holdout; painéis têm escalas diferentes.")]
    cells=[nbformat.v4.new_markdown_cell("# Fase 7 — Final holdout evaluation\n\nPrimeira abertura analítica autorizada de eval após o commit `d6681aa`. "
        "Previsões de sete dias congeladas antes dos actuals, modelos e regras inalterados. "
        "Notebook consome outputs: nenhuma leitura de raw, ajuste, tuning ou transformação crítica exclusiva de célula."),
        nbformat.v4.new_code_cell("%matplotlib inline\nfrom pathlib import Path\nimport sys\nroot=Path.cwd()\n"
        "if not (root/'src').is_dir():\n    root=root.parent\nsys.path.insert(0,str(root))\n"
        "import matplotlib.pyplot as plt\nfrom IPython.display import display\n"
        "from src.reporting.holdout_report import load_outputs\nfrom src.reporting.holdout_plots import PLOTS,save_figure\n"
        "data=load_outputs(root)\nassert data['summary']['source_split']=='eval'\n"
        "assert data['summary']['n_fits']==50000\nassert data['summary']['n_forecasts_per_model']==350000")]
    extras={1:"display(data['paired_comparison'].loc[lambda x:x.level.eq('global')])",
        6:"display(data['persistence_retention'])",9:"display(data['uncertainty_association'])",
        10:"display(data['low_scale'])\ndisplay(data['contemporary_stockout'])"}
    for i,(title,note) in enumerate(topics,1):
        cells.append(nbformat.v4.new_markdown_cell(f"## {i}. {title}\n\n{note}"))
        cells.append(nbformat.v4.new_code_cell(f"fig=PLOTS[{i-1}](data)\nsave_figure(fig,{i},root)\nplt.show()\n"+extras.get(i,"")))
    assessment=read_json(ROOT/FOLDER/"assessment.json")
    cells.append(nbformat.v4.new_markdown_cell("## Conclusão congelada após avaliação\n\n**"+assessment['classification']+"**\n\n"+
        assessment['reasoning']+"\n\n"+assessment['risk_interpretation']+"\n\nUma semana não prova estabilidade futura. Eval não será reutilizado para retuning. Sem reposição ou Power BI."))
    for i,cell in enumerate(cells):
        cell["id"]=f"phase7-cell-{i:02d}"
    notebook=nbformat.v4.new_notebook(cells=cells,metadata={"kernelspec":{"display_name":"Python 3 (project .venv)","language":"python","name":"python3"}})
    manager=KernelManager(kernel_name="python3")
    manager.kernel_spec.argv=[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"]
    client=NotebookClient(notebook,km=manager,timeout=180,record_timing=False,resources={"metadata":{"path":str(ROOT)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    path=ROOT/"notebooks/06_final_holdout_evaluation.ipynb"
    nbformat.write(notebook,path)
    write_json(ROOT/FOLDER/"notebook_performance.json",{"seconds":perf_counter()-started,"notebook_bytes":path.stat().st_size,"figures":10})
    print("Notebook final executado: dez figuras, nenhum ajuste ou acesso a raw.",flush=True)


if __name__=="__main__":
    main()
