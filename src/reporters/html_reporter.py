from pathlib import Path
from typing import Any, Union


class HTMLReporter:

    @classmethod
    def generate(cls, result: Any, target_path: Union[str, Path]) -> Path:
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        status_color = "#2e7d32" if result.is_valid else "#c62828"
        status_text = "УСПЕШНО" if result.is_valid else "ОБНАРУЖЕНЫ ОШИБКИ"

        rows_html = []
        for item in result.errors_table:
            val_display = str(item.get("value", ""))
            if len(val_display) > 60:
                val_display = val_display[:57] + "..."
            rows_html.append(
                f"<tr>"
                f"<td style='text-align:center;'>{item['row']}</td>"
                f"<td><b>{item['field']}</b></td>"
                f"<td><code>{val_display}</code></td>"
                f"<td><span style='background:#f5f5f5;padding:2px 6px;border-radius:4px;'>{item['rule']}</span></td>"
                f"<td>{item['message']}</td>"
                f"</tr>"
            )

        table_content = "\n".join(rows_html)
        if rows_html:
            error_section = f"""
            <h3>Список ошибок валидации ({len(result.errors_table)})</h3>
            <table style="width:100%; border-collapse: collapse; margin-top: 10px;">
                <thead>
                    <tr style="background:#f0f0f0; text-align:left;">
                        <th style="padding:8px; border:1px solid #ddd; text-align:center;">Строка</th>
                        <th style="padding:8px; border:1px solid #ddd;">Поле</th>
                        <th style="padding:8px; border:1px solid #ddd;">Значение</th>
                        <th style="padding:8px; border:1px solid #ddd;">Правило</th>
                        <th style="padding:8px; border:1px solid #ddd;">Сообщение</th>
                    </tr>
                </thead>
                <tbody>
                    {table_content}
                </tbody>
            </table>
            """
        else:
            error_section = "<p style='color:#2e7d32;font-size:16px;'>Все записи прошли валидацию без ошибок.</p>"

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>DataBridge - Отчёт валидации</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 30px; color: #333; }}
        .header {{ border-bottom: 2px solid #ddd; padding-bottom: 15px; margin-bottom: 20px; }}
        .badge {{ display: inline-block; padding: 6px 12px; border-radius: 4px; color: #fff; font-weight: bold; background: {status_color}; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }}
        .card {{ background: #fafafa; border: 1px solid #e0e0e0; padding: 15px; border-radius: 6px; }}
        .card-value {{ font-size: 24px; font-weight: bold; margin-top: 5px; }}
        table td, table th {{ padding: 8px 12px; border: 1px solid #e0e0e0; }}
        tr:nth-child(even) {{ background: #fdfdfd; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>Отчёт валидации данных (DataBridge)</h2>
        <span class="badge">{status_text}</span>
    </div>
    <div class="stats-grid">
        <div class="card">Всего записей:<div class="card-value">{result.total_records}</div></div>
        <div class="card">Успешно обработано:<div class="card-value" style="color:#2e7d32;">{result.valid_count}</div></div>
        <div class="card">Записей с ошибками:<div class="card-value" style="color:#c62828;">{len(result.invalid_indices)}</div></div>
    </div>
    {error_section}
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return target
