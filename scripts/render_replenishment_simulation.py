"""Render the Phase 8 outputs-only notebook and report, without fitting or raw."""

import os
from pathlib import Path
import sys
from time import perf_counter

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from src.replenishment.simulation import FOLDER, write_json
    from src.reporting.replenishment_report import write_report
    started = perf_counter()
    write_report(ROOT)
    runtime = ROOT / ".tmp/jupyter_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"] = str(runtime)
    os.environ["IPYTHONDIR"] = str(ROOT / ".ipython")
    os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
    topics = [
        ("Validação temporal", "Calibração folds 1–3, escala de 21 erros e rótulos prospectivos. Fold 4 não escolhe nem retuna a política. Gaps negativos permanecem explícitos."),
        ("Multiplicadores finais", "Quatro folds de train; Normal é apenas benchmark. Caudas empíricas não representam fill rate ou serviço real."),
        ("Safety stock simulado", "Reservas hipotéticas na escala normalizada. Não inferir unidades físicas ou demanda latente."),
        ("Reorder point simulado", "Limiar = forecast acumulado + buffer. Não é estoque disponível, ordem de compra ou quantidade a comprar."),
        ("ABC", "Ratios individuais excluem denominadores zero e diferem do ratio de somas. ABC é relevância de venda observada, não receita."),
        ("XYZ", "Classes finais conhecidas em 25/06; calibração histórica usa os snapshots prospectivos de cada fold."),
        ("Exposição", "Exposição é dimensão histórica de pooling; flags de censura e persistência não multiplicam buffer."),
        ("A e duplo sinal", "Investigar coexistência de relevância, incerteza e sinais de observação. Nenhuma compra automática."),
        ("Suporte e fallback", "Hierarquia ABC×XYZ×exposure → ABC×XYZ → XYZ → GLOBAL, mínimo de 20 observações esperadas na cauda; correlação reduz informação efetiva."),
        ("Exemplos", "Sete exemplos da Fase 6, sem seleção manual. Cenários variam L e q simultaneamente; não há cenário vencedor identificado."),
    ]
    cells = [nbformat.v4.new_markdown_cell(
        "# Fase 8 — Simulação de política de reposição\n\n"
        "Forecasting congelado em `3c52827`: **zero fitting ETS e nenhum actual eval**. "
        "Somente outputs desta simulação são carregados aqui. Cenários L1/q90, L2/q95 e L3/q98 são hipóteses. "
        "O target é cobertura histórica de venda observada normalizada; não é fill rate, OTIF ou garantia de ausência de ruptura. "
        "Sem inventário completo, pedidos, fornecedores, custos ou Power BI."),
        nbformat.v4.new_code_cell(
            "%matplotlib inline\nfrom pathlib import Path\nimport sys\n"
            "root=Path.cwd()\nif not (root/'src').is_dir():\n    root=root.parent\nsys.path.insert(0,str(root))\n"
            "import matplotlib.pyplot as plt\nfrom IPython.display import display\n"
            "from src.reporting.replenishment_report import load_outputs\n"
            "from src.reporting.replenishment_plots import PLOTS, save_figure\n"
            "data=load_outputs(root)\nassert data['metadata']['n_ets_fits']==0\n"
            "assert data['metadata']['eval_actuals_read'] is False\nassert len(data['simulation'])==150000\n"
            "display(data['dependence'])")]
    for index, (title, note) in enumerate(topics, 1):
        cells.append(nbformat.v4.new_markdown_cell(f"## {index}. {title}\n\n{note}"))
        extra = ""
        if index == 1:
            extra = "display(data['summary'].loc[lambda x: x.stage.eq('validation_fold4') & x.level.eq('global'), ['scenario','target_coverage_level','observed_coverage_rate','coverage_gap','normal_coverage_rate']])\n"
        if index == 9:
            extra = "display(data['fallback_distribution'])\n"
        cells.append(nbformat.v4.new_code_cell(
            f"fig=PLOTS[{index-1}](data)\nsave_figure(fig,{index},root)\nplt.show()\n" + extra))
    cells.append(nbformat.v4.new_markdown_cell(
        "## Limites e conclusão\n\n"
        "A validação temporal revela subcobertura nos três cenários; não ajustar quantis após esse resultado. "
        "O snapshot final usa quatro folds já conhecidos em 25/06 e não tem cobertura futura comprovada. "
        "A simulação é auditável e descritiva; **os alvos não foram atingidos no fold 4**. "
        "Não recomendar política real ou compra. Consultar o relatório, protocolo e hashes. "
        "Equivalência em dias é apenas ROP dividido pela média prevista de sete dias. Sem commit ou Power BI."))
    for index, cell in enumerate(cells):
        cell["id"] = f"phase8-cell-{index:02d}"
    notebook = nbformat.v4.new_notebook(cells=cells, metadata={"kernelspec": {
        "display_name": "Python 3 (project .venv)", "language": "python", "name": "python3"}})
    manager = KernelManager(kernel_name="python3")
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(notebook, km=manager, timeout=180, record_timing=False,
                            resources={"metadata": {"path": str(ROOT)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    path = ROOT / "notebooks/07_replenishment_simulation.ipynb"
    nbformat.write(notebook, path)
    write_json(ROOT / FOLDER / "notebook_performance.json", {
        "seconds": perf_counter() - started, "notebook_bytes": path.stat().st_size, "figures": 10})
    print("Phase 8 report and notebook: ten figures, outputs only, zero fitting.", flush=True)


if __name__ == "__main__":
    main()
