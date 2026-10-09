"""Executa dez figuras da Fase 6, usando somente os outputs persistidos."""

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
    started=perf_counter()
    runtime=ROOT / ".tmp/jupyter_runtime"
    runtime.mkdir(parents=True,exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"]=str(runtime)
    os.environ["IPYTHONDIR"]=str(ROOT / ".ipython")
    os.environ["MPLCONFIGDIR"]=str(ROOT / ".matplotlib")
    topics=[
        ("Distribuição de bias","Cada série agrega 28 dias. Bias negativo não comprova ruptura ou demanda perdida."),
        ("Incerteza empírica","Desvio amostral, RMSE, p90 e p95 absolutos. Caudas por série têm amostra pequena; não são intervalos probabilísticos."),
        ("Persistência e frequência","Regra oficial: bias consolidado<0 e pelo menos três folds negativos. Frequência de dias subprevistos é outra dimensão."),
        ("Exposição à ruptura","Comparação descritiva pelas classes conhecidas em 25/06. Escala explica por que maior erro absoluto pode coexistir com menor WAPE."),
        ("Possível censura","Flag preservada da Fase 3. Erros maiores e bias mais negativo não significam necessariamente mais dias subprevistos."),
        ("Matriz de dois sinais","Nenhum score. NEITHER é ausência dos dois sinais específicos, não ausência de todo risco."),
        ("Matriz por ABC","A/B com duplo sinal são recortes para investigação posterior, sem recomendação de compra. Venda normalizada não é receita."),
        ("Incerteza por XYZ","Quantis/desvios calculados das observações agrupadas. As classes finais não são tratadas como conhecidas em origens anteriores."),
        ("Exemplos reproduzíveis","Quatro exemplos A próximos à mediana de error_std de cada célula; máximos de desvio/taxa em A; menor MAE entre LOW. Desempates por IDs. Linhas verticais separam os folds."),
        ("Robustez","Omitir fold 4 inverte o bias global. Remover p1/p99 reduz bastante RMSE. São análises separadas; todos os erros permanecem nos resultados oficiais."),
    ]
    cells=[nbformat.v4.new_markdown_cell(
        "# Fase 6 — Incerteza do forecast e risco da observação da demanda\n\n"
        "**Somente outputs derivados de train. Eval fechado. ETS e forecasts preservados.**\n\n"
        "Perfis em 25/06/2024, disponíveis após essa data. Labels da Fase 3 são usados para diagnóstico "
        "retrospectivo e não podem ser reutilizados dentro dos folds anteriores como informação já conhecida. "
        "Não há reconstrução de demanda, lost sales, intervalo probabilístico ou fórmula de safety stock.\n\n"
        "Lógica em src; relatório `docs/forecast_uncertainty_and_risk_report.md`."),
        nbformat.v4.new_code_cell(
        "%matplotlib inline\nfrom pathlib import Path\nimport sys\nroot = Path.cwd()\n"
        "if not (root / 'src').is_dir():\n    root = root.parent\nsys.path.insert(0, str(root))\n"
        "import matplotlib.pyplot as plt\nfrom IPython.display import display\n"
        "from src.reporting.demand_risk_report import load_outputs\n"
        "from src.reporting.demand_risk_plots import PLOTS, save_figure\n"
        "data = load_outputs(root)\nassert data['summary']['source_split'] == 'train'\n"
        "assert data['summary']['n_fits_performed'] == 0\n"
        "assert data['summary']['available_from'] == '2024-06-26'\n"
        "display(data['calibration'].loc[data['calibration'].level.eq('global')])")]
    for number,(title,comment) in enumerate(topics,1):
        source=f"fig = PLOTS[{number-1}](data)\nsave_figure(fig, {number}, root)\ndisplay(fig)\nplt.close(fig)"
        if number==3:
            source+="\ndisplay(data['persistence_distribution'])\ndisplay(data['persistence_sensitivity'])"
        if number==6:
            source+="\ndisplay(data['high_uncertainty_diagnostics'])"
        if number==10:
            source+="\ndisplay(data['persistence_retention'])\ndisplay(data['low_scale_diagnostics'])"
        cells.extend([nbformat.v4.new_markdown_cell(f"## {number:02d}. {title}\n\n{comment}"),nbformat.v4.new_code_cell(source)])
    cells.append(nbformat.v4.new_markdown_cell(
        "## Interpretação e limites\n\n"
        "16.529 séries são persistentes (33,058%); 1.028 combinam persistência e possível censura. "
        "A + duplo sinal reúne 706 séries e 1,641% da venda normalizada train. "
        "518 séries com duplo sinal têm error_std no quartil superior global, incluindo 398 A.\n\n"
        "A flag de censura está associada a maior magnitude de erro e bias mais negativo; a frequência de "
        "subprevisão é semelhante (50,09% com flag; 50,23% sem). Não há inferência causal. "
        "A composição da matriz usa o próprio erro na definição da persistência; separação de bias não é "
        "validação independente de poder preditivo.\n\n"
        "O bias global depende do último fold, mas 90,59% dos persistentes mantêm bias negativo sem ele. "
        "28 observações limitam p90/p95; as séries compartilham loja/produto/calendário. "
        "Apenas diagnóstico: nenhuma escolha de safety stock, correção de forecast ou abertura do holdout."))
    for i,cell in enumerate(cells):
        cell["id"]=f"phase6-cell-{i:02d}"
    notebook=nbformat.v4.new_notebook(cells=cells,metadata={"kernelspec":{
        "display_name":"Python 3 (project .venv)","language":"python","name":"python3"}})
    manager=KernelManager(kernel_name="python3")
    manager.kernel_spec.argv=[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"]
    client=NotebookClient(notebook,km=manager,timeout=180,record_timing=False,resources={"metadata":{"path":str(ROOT)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    path=ROOT / "notebooks/05_forecast_uncertainty_and_risk.ipynb"
    nbformat.write(notebook,path)
    write_json(ROOT / "data/outputs/forecast_uncertainty/notebook_performance.json",{
        "seconds":perf_counter()-started,"notebook_bytes":path.stat().st_size,"figures":10})
    print("Notebook Fase 6 executado: dez figuras; nenhum refit.")


if __name__=="__main__":
    main()
