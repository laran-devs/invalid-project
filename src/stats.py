"""Модуль профилирования и сбора статистики по датасетам."""

import pandas as pd


def format_bytes(size: int) -> str:
    """Форматирует размер в байтах в человекочитаемый вид."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def get_dataframe_stats(df: pd.DataFrame, file_size: int = 0) -> str:
    """Формирует текстовый отчёт со статистикой по DataFrame."""
    total_rows, total_cols = df.shape
    mem_usage = df.memory_usage(deep=True).sum()

    lines = []
    lines.append("=" * 72)
    lines.append("  СТАТИСТИКА ДАННЫХ (DATA STATISTICS)")
    lines.append("=" * 72)
    lines.append(f"  Строк (Rows):        {total_rows}")
    lines.append(f"  Колонок (Columns):   {total_cols}")
    if file_size > 0:
        lines.append(f"  Размер файла:        {format_bytes(file_size)}")
    lines.append(f"  Объём в памяти:      {format_bytes(mem_usage)}")
    lines.append("-" * 72)

    col_w = 18
    type_w = 10
    non_null_w = 10
    null_pct_w = 8
    uniq_w = 8

    lines.append(
        f"  {'Колонка':<{col_w}} "
        f"{'Тип':<{type_w}} "
        f"{'Заполнено':<{non_null_w}} "
        f"{'Пропуски':<{null_pct_w}} "
        f"{'Уникально':<{uniq_w}} "
        f"{'Числовые параметры'}"
    )
    lines.append("  " + "-" * 68)

    for col in df.columns:
        series = df[col]
        non_null = int(series.count())
        null_pct = f"{(series.isna().mean() * 100):.1f}%"
        unique_cnt = int(series.nunique(dropna=True))
        dtype_str = str(series.dtype)

        extra = ""
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            valid_nums = series.dropna()
            if not valid_nums.empty:
                min_v = round(float(valid_nums.min()), 2)
                max_v = round(float(valid_nums.max()), 2)
                mean_v = round(float(valid_nums.mean()), 2)
                extra = f"min={min_v}, max={max_v}, avg={mean_v}"

        col_display = str(col)[: col_w - 1]
        lines.append(
            f"  {col_display:<{col_w}} "
            f"{dtype_str:<{type_w}} "
            f"{non_null:<{non_null_w}} "
            f"{null_pct:<{null_pct_w}} "
            f"{unique_cnt:<{uniq_w}} "
            f"{extra}"
        )

    lines.append("=" * 72)
    return "\n".join(lines)
