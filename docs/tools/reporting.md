# Reporting Tools

## Coverage

- Covers baseline execution for `PortfolioComposerText`, `PortfolioComposerTable`, `PortfolioComposerImage`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `ReportMap`, and `PlotlyCharting`.
- Emits a deterministic one-row `Report` fragment from reporting tools with an `Output` anchor.
- Records report type, source row count, source columns, and normalized config metadata.
- Treats `PortfolioComposerRender` as a sink that records render options and input schemas without writing files.

## Deferred

- Native PDF, DOCX, PNG, map, image, and interactive Plotly rendering is not implemented.
- Visual styling, pagination, embedded images, map layers, and chart rendering are preserved as config metadata only.
- Exact Alteryx report-snippet binary formats remain out of scope for the Python baseline.
