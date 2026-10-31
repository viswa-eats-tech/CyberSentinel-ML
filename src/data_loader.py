from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

TARGET_COLUMN = "label"
ATTACK_CATEGORY_COLUMN = "attack_cat"
ID_COLUMN = "id"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def workspace_root() -> Path:
    return project_root().parent


def default_dataset_dir() -> Path:
    env_path = os.getenv("UNSW_NB15_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()

    return (
        workspace_root()
        / "UNSW-NB15 dataset"
        / "CSV Files"
        / "Training and Testing Sets"
    )


def training_csv_path(dataset_dir: Path | None = None) -> Path:
    return (dataset_dir or default_dataset_dir()) / "UNSW_NB15_training-set.csv"


def testing_csv_path(dataset_dir: Path | None = None) -> Path:
    return (dataset_dir or default_dataset_dir()) / "UNSW_NB15_testing-set.csv"


def load_training_data(dataset_dir: Path | None = None) -> pd.DataFrame:
    return _load_csv(training_csv_path(dataset_dir))


def load_testing_data(dataset_dir: Path | None = None) -> pd.DataFrame:
    return _load_csv(testing_csv_path(dataset_dir))


def split_features_target(
    data: pd.DataFrame,
    drop_columns: Iterable[str] = (ID_COLUMN, ATTACK_CATEGORY_COLUMN),
) -> tuple[pd.DataFrame, pd.Series]:
    excluded_columns = tuple(drop_columns)
    if TARGET_COLUMN not in data.columns:
        raise ValueError(f"Missing required target column: {TARGET_COLUMN}")

    feature_data = data.drop(
        columns=[
            col for col in [TARGET_COLUMN, *excluded_columns] if col in data.columns
        ]
    )
    target = data[TARGET_COLUMN].astype(int)
    return feature_data, target


def feature_groups(data: pd.DataFrame) -> tuple[list[str], list[str]]:
    excluded = {TARGET_COLUMN, ATTACK_CATEGORY_COLUMN, ID_COLUMN}
    feature_data = data.drop(columns=[col for col in excluded if col in data.columns])
    categorical = feature_data.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()
    numeric = [col for col in feature_data.columns if col not in categorical]
    return numeric, categorical


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {path}. "
            "Set UNSW_NB15_DATA_DIR if the dataset is stored elsewhere."
        )

    return pd.read_csv(path, encoding="utf-8-sig")
