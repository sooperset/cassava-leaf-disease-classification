import pytorch_lightning as pl
from hydra.utils import to_absolute_path
from typing import Tuple, List, Optional
from omegaconf import DictConfig, OmegaConf

import os
import pandas as pd
import logging
from omegaconf import DictConfig, OmegaConf
import hydra
from hydra.utils import instantiate
from pytorch_lightning.utilities.seed import seed_everything

from sklearn.model_selection import StratifiedKFold
from torch.utils.data import DataLoader
from dataset.transforms import get_transforms
from dataset.cassava import CassavaDataset


class DataModule(pl.LightningDataModule):
    def __init__(
        self,
        train_data_dir: str,
        val_data_dir: str,
        df_path: str,
        train_dataset_conf: Optional[DictConfig] = None,
        val_dataset_conf: Optional[DictConfig] = None,
        train_dataloader_conf: Optional[DictConfig] = None,
        val_dataloader_conf: Optional[DictConfig] = None,
        fold_num: int = None,
    ):
        super().__init__()
        self.fold_num = fold_num if fold_num is not None else 0
        self.train_data_dir = train_data_dir
        self.val_data_dir = val_data_dir
        self.df_path = df_path
        self.train_dataset_conf = train_dataset_conf or OmegaConf.create()
        self.val_dataset_conf = val_dataset_conf or OmegaConf.create()
        self.train_dataloader_conf = train_dataloader_conf or OmegaConf.create()
        self.val_dataloader_conf = val_dataloader_conf or OmegaConf.create()

    def setup(self, stage: Optional[str] = None):
        if stage == "fit" or stage is None:
            df = pd.read_csv(self.df_path)
            skf = StratifiedKFold(n_splits=5, shuffle=True)
            df.loc[:, 'fold'] = 0
            for fold_num, (train_index, val_index) in enumerate(skf.split(X=df.index, y=df.label.values)):
                df.loc[df.iloc[val_index].index, 'fold'] = fold_num

            train_df = df[df.fold != self.fold_num].reset_index(drop=True)
            val_df = df[df.fold == self.fold_num].reset_index(drop=True)
            self.train = CassavaDataset(self.train_data_dir, train_df, train=True,
                                        **self.data_conf.train_dataset_conf)
            self.val = CassavaDataset(self.val_data_dir, val_df, train=False,
                                      **self.data_conf.val_dataset_conf)

        if stage == "test" or stage is None:
            pass

    def train_dataloader(self):
        return DataLoader(self.train, **self.data_conf.train_dataloader_conf)

    def val_dataloader(self):
        return DataLoader(self.val, **self.data_conf.val_dataloader_conf)

    def test_dataloader(self):
        return self.val_dataloader