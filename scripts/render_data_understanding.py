"""Cria/executa o notebook de apresentação; não recalcula métricas nem lê raw."""

import os
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parents[1]


def main():
    runtime = ROOT / ".tmp/jupyter_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"] = str(runtime)
    os.environ["IPYTHONDIR"] = str(ROOT / ".ipython")
    os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
    titles = [
        ("Nível e variabilidade", "A distribuição de médias é assimétrica. CV é descritivo e mistura disponibilidade, promoção e variação de venda."),
        ("Concentração", "Compare a participação de produtos, lojas e pares loja-produto. A linha de 80% é referência de leitura; nenhuma classe ABC foi atribuída."),
        ("Zeros e ADI", "Observe toda a distribuição. ADI e zero_ratio são redundantes nesta janela completa; zeros podem coincidir com ruptura."),
        ("Perfil por dia da semana", "Médias por observação corrigem a contagem desigual de weekdays. A faixa relativa mostra diferenças entre séries, sem teste causal."),
        ("Estabilidade semanal", "Correlação lag 7 e semelhança entre metades avaliam aspectos diferentes. Correlação positiva não é garantia de previsão nem evidência de sazonalidade anual."),
        ("Exposição à ruptura", "A janela do contador é [06h,22h). Frequência e duração devem acompanhar qualquer leitura de venda observada."),
        ("Ruptura dentro das séries", "A diagonal indica igualdade das médias. Cada célula agrega séries; não há amostragem visual. No outro painel, 16 horas de ruptura concentram zeros."),
        ("Atividade e desconto", "A comparação é dentro da série, mas não controla calendário ou seleção da promoção. Os 34 discount > 1 permanecem nos dados; a listagem completa está no relatório."),
        ("Exemplos reproduzíveis", "Filtros p25/p75 de train e extremos de CV/zeros; desempate por loja e produto. Regras e identificadores estão em summary.json, sem escolha manual."),
    ]
    cells=[nbformat.v4.new_markdown_cell(
        "# Fase 2 — Entendimento da venda observada\n\n"
        "**Somente train: 28/03 a 25/06/2024. Eval permanece congelado.**\n\n"
        "Venda normalizada não equivale a demanda latente nem a unidades físicas. "
        "Este notebook contém nove figuras e consome apenas os outputs do script "
        "`python scripts/build_demand_profile.py`. Fórmulas e seleção de exemplos ficam em SQL/src; "
        "não há transformação crítica exclusiva aqui. Consulte `docs/demand_understanding_report.md` "
        "para tabelas completas e `docs/methodology.md` para definições."),
        nbformat.v4.new_code_cell(
        "%matplotlib inline\nfrom pathlib import Path\nimport sys\n"
        "root = Path.cwd()\nif not (root / 'src').is_dir():\n    root = root.parent\n"
        "sys.path.insert(0, str(root))\n"
        "import matplotlib.pyplot as plt\nfrom IPython.display import display\n"
        "from src.reporting.demand_understanding_plots import load_outputs, PLOTS, save_figure\n"
        "data = load_outputs(root)\n"
        "assert data['summary']['source_split'] == 'train'\n"
        "print(f\"{data['summary']['overview']['n_series']:,} séries; fonte: {data['summary']['source']['path']}\")")]
    for number,(title,comment) in enumerate(titles,1):
        cells.append(nbformat.v4.new_markdown_cell(f"## {number:02d}. {title}\n\n{comment}"))
        cells.append(nbformat.v4.new_code_cell(
            f"fig = PLOTS[{number-1}](data)\nsave_figure(fig, {number}, root)\ndisplay(fig)\nplt.close(fig)"))
    for index,cell in enumerate(cells):
        cell["id"]=f"phase2-cell-{index:02d}"
    notebook=nbformat.v4.new_notebook(cells=cells,metadata={
        "kernelspec":{"display_name":"Python 3 (project .venv)","language":"python","name":"python3"}})
    manager=KernelManager(kernel_name="python3")
    manager.kernel_spec.argv=[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"]
    client=NotebookClient(notebook,km=manager,timeout=180,record_timing=False,resources={"metadata":{"path":str(ROOT)}})
    # O kernel usa explicitamente o mesmo Python/.venv do script.
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    path=ROOT / "notebooks/01_data_understanding.ipynb"
    nbformat.write(notebook,path)
    print(f"Notebook executado: {path}; nove figuras PNG em outputs.")


if __name__ == "__main__":
    main()
