from enum import Enum
from typing import Any, Callable

import pandas as pd
import dask.dataframe as dd
import numpy as np

class Level(Enum):
    CATEGORY = 'category'
    ATTACK = 'attack'

class Mode(Enum):
    EXC = 'exc'
    INC = 'inc'


# note: All type Pandas type hints may be Dask types at runtime. Unfortunately Dask does not support type hints.
class FilteredDataset:
    def __init__(self, dataset: pd.DataFrame, category_col_name: str, attack_col_name: str, benign_encoding:Any=0) -> None:
        self._dataset: pd.DataFrame = dataset
        self.col_labels: dict[Level, str] = {Level.CATEGORY: category_col_name, Level.ATTACK: attack_col_name}
        self.benign_encoding = benign_encoding

        self.op: dict[Mode, Callable[[pd.Series, str], pd.Series]] = {
        Mode.EXC: lambda dataset_labels, label: dataset_labels != label, 
        Mode.INC: lambda dataset_labels, label: (dataset_labels == label) + (dataset_labels == self.benign_encoding)
    }

    def get_variant_index(self, level: Level, mode: Mode, label:Any) -> pd.Index:
        labels_col_name: str = self.col_labels[level]
        dataset_labels: pd.Series = self._dataset[labels_col_name]
        mask = self.op[mode](dataset_labels, label)
        return  self._dataset.index[mask]
    
    def get_variants_index(self, level: Level, mode: Mode) -> list[tuple[pd.Index, str]]:
        labels_col_name: str = self.col_labels[level]
        labels: np.ndarray = self._dataset[labels_col_name].unique()
        return [(self.get_variant_index(level, mode, label), label) for label in labels if label != self.benign_encoding]

    def get_variant(self, level: Level, mode: Mode, label:Any) -> pd.DataFrame:
        labels_col_name: str = self.col_labels[level]
        dataset_labels: pd.Series = self._dataset[labels_col_name]
        mask = self.op[mode](dataset_labels, label)
        return  self._dataset[mask]

    def get_variants(self, level: Level, mode: Mode) -> list[tuple[pd.DataFrame, str]]:
        labels_col_name: str = self.col_labels[level]
        labels: np.ndarray = self._dataset[labels_col_name].unique()
        return [(self.get_variant(level, mode, label), label) for label in labels if label != self.benign_encoding]

    def get_all_variants(self) -> list[tuple[list[tuple[pd.DataFrame, str]], tuple[Level, Mode]]]:
        return [(self.get_variants(l, m), (l,m)) for l in Level for m in Mode]
