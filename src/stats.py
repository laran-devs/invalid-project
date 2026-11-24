import pandas as pd


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def get_dataframe_stats(df: pd.DataFrame, file_size: int = 0) -> str:
    from .reporters import StatsReporter
    return StatsReporter.get_stats(df, file_size=file_size)
