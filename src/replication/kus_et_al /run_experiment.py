import subprocess
import argparse
import os
# import sys  # uncomment to use a specific GPU for BLSTM model
# sys.path.append('external_repos/ML-NIDS-for-SCADA/src')
import platform
from typing import Callable
is_unix =  platform.system() in ['Linux', 'Darwin']
if not is_unix:
    import shutil

import numpy as np
import pandas as pd
import tensorflow as tf

from post_cleaning import clean_interim_data, clean_weights

from data.filtered_dataset import FilteredDataset, Level, Mode
# from bidirectional_lstm import main  # uncomment to use a specific GPU for BLSTM model

def _infer_category(attack_id: int) -> int:
    if attack_id < 0 or attack_id > 35:
        raise ValueError('Invalid attack ID')
    elif attack_id == 0:
        return 0
    elif attack_id <= 12:
        return 4
    elif attack_id <= 17:
        return 3
    elif attack_id == 18:
        return 6
    elif attack_id in [20,23,24]:
        return 7
    elif attack_id in [19,21,22]:
        return 5
    elif 29 <= attack_id <= 32:
        return 1
    else:
        return 2
infer_categories = np.vectorize(_infer_category)

if is_unix:
    copy = os.link
else:
    copy = shutil.copy

def cp(src: str, dest: str, level: Level, model: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for file in os.listdir(src):
        if 'test' in file and 'npy' in file:
            if level == Level.CATEGORY and 'Y' in file:
                ys: np.ndarray = np.load(os.path.join(src, file))
                if model == 'blstm':
                    ys =np.argmax(ys, axis=1)
                ys1 = infer_categories(ys.ravel())
                if model != 'blstm':
                    ys1.reshape(-1, 1)
                else:
                    label_no = 8 if level == Level.CATEGORY else 36
                    ys1 = np.eye(label_no)[ys1]
                np.save(os.path.join(dest, file), ys1)
            else:
                path: str = os.path.join(dest, file)
                if os.path.exists(path):
                    os.remove(path)
                copy(os.path.join(src, file), os.path.join(dest, file))

def filter_dataset(dataset_dir: str, model: str) -> tuple[FilteredDataset, FilteredDataset, FilteredDataset]:
    # data loading script taken from ML-NIDS-for-SCADA repository
    dataset_filenames = [
        'Xs_train.npy', 'Xs_val.npy', 'Xs_test.npy', 'Xs_train_val.npy', 'Xs_train_test.npy',
        'Ys_train.npy', 'Ys_val.npy', 'Ys_test.npy', 'Ys_train_val.npy', 'Ys_train_test.npy'
    ]

    dataset_filenames = map(lambda x: os.path.join(dataset_dir, x), dataset_filenames)
    X_train, X_val, _, X_train_val, _, Y_train, Y_val, _, Y_train_val, _ = map(np.load, dataset_filenames)

    if model == 'blstm':
        Y_train, Y_val, Y_train_val = np.argmax(Y_train, axis=1), np.argmax(Y_val, axis=1), np.argmax(Y_train_val, axis=1)

    # generate variants
    cat: str = Level.CATEGORY.value
    att: str = Level.ATTACK.value

    df_train: pd.DataFrame = pd.concat([pd.DataFrame(X_train), pd.Series(infer_categories(Y_train.ravel()), name=cat), pd.Series(Y_train.ravel(), name=att, dtype=int)], axis=1)
    train: FilteredDataset = FilteredDataset(df_train, cat, att) # TODO: specify benign encoding
    
    df_val: pd.DataFrame = pd.concat([pd.DataFrame(X_val), pd.Series(infer_categories(Y_val.ravel()), name=cat), pd.Series(Y_val.ravel(), name=att, dtype=int)], axis=1)
    val: FilteredDataset = FilteredDataset(df_val, cat, att)
    
    df_train_val = pd.concat([pd.DataFrame(X_train_val), pd.Series(infer_categories(Y_train_val.ravel()), name=cat), pd.Series(Y_train_val.ravel(), name=att, dtype=int)], axis=1)
    train_val = FilteredDataset(df_train_val, cat, att)

    return train, val, train_val

def write_dataset(dataset_dir, df_train, df_val, df_train_val, level: Level):
    # data saving script taken from ML-NIDS-for-SCADA repository
    np.save(os.path.join(dataset_dir, 'Xs_train'), df_train.iloc[:, :-2].values)
    np.save(os.path.join(dataset_dir, 'Xs_val'),   df_val.iloc[:, :-2].values)
    np.save(os.path.join(dataset_dir, 'Xs_train_val'), df_train_val.iloc[:, :-2].values)

    ys_train = df_train[level.value].values
    ys_val = df_val[level.value].values
    ys_train_val = df_train_val[level.value].values
    
    if model != 'blstm':
        ys_train.reshape(-1, 1)
        ys_val.reshape(-1, 1)
        ys_train_val.reshape(-1, 1)
    else:
        label_no = 8 if level == Level.CATEGORY else 36
        ys_train, ys_val, ys_train_val = np.eye(label_no)[ys_train_val], np.eye(label_no)[ys_val], np.eye(label_no)[ys_train_val]
    np.save(os.path.join(dataset_dir, 'Ys_train'), ys_train)
    np.save(os.path.join(dataset_dir, 'Ys_val'), ys_val)
    np.save(os.path.join(dataset_dir, 'Ys_train_val'), ys_train_val)

REPOSITORY_ROOT = './external_repos/ML-NIDS-for-SCADA'
PRE_PROCESS_CMD = lambda path, type, args: f'python {REPOSITORY_ROOT}/src/preprocess-data_{type}.py -d {path} --time-series --split 0.6 0.2 0.2 --encode-function --label dcategory -n mean '+args

STD_DIR = 'normal-datasets'
TS_DIR = 'time-series-datasets'        

if __name__ == '__main__':
    # arg parsing
    parser = argparse.ArgumentParser(description='Replicates experiments of Kus et al.')
    parser.add_argument('-r', '--ml-nids-root', type=str, help='Root directory of ML-NIDS-for-SCADA git repository')
    args = parser.parse_args()
    if args.ml_nids_root:
        REPOSITORY_ROOT = args.r

    # output directory setup
    output_dir = 'output'

    # Run model command
    model_cmd = {'svm':'svm_testset', 'rf': 'random_forest_testset', 'blstm':'bidirectional_lstm'}
    payload = {'svm':'--payload-keep-value-imputed', 'rf': '--payload-keep-value-imputed', 'blstm':'--payload-indicator-imputed'}

    for model in ('rf', 'svm', 'blstm'):
        # if model != 'blstm':  # uncommne tot use specific GPU for BLSTM model
        #     continue
        # setup data folder
        model_dir = os.path.join(output_dir, model)
        data_path = os.path.join(model_dir, 'data')
        os.makedirs(data_path, exist_ok=True)
        
        # preprocess dataset for model
        setup_cmd: str = PRE_PROCESS_CMD(f'{REPOSITORY_ROOT}/data/IanArffDataset.arff', model, f'{payload[model]} -o {data_path}')
        subprocess.run(setup_cmd.split())

        train, val, train_val= filter_dataset(data_path, model)
        
        # run model on whole dataset as baseline
        # subprocess.run(f'python {REPOSITORY_ROOT}/src/{model_cmd[model]}.py -d {data_path} -i 1'.split())
        # exit(0)
        
        # run model on all variants
        for exp_class_train, (level, mode) in train.get_all_variants():
            for experiment, label in exp_class_train:
                if label == 0: continue
                if level == Level.CATEGORY: continue
                # working directory setup
                cwd = '-'.join((level.value, mode.value, str(label)))
                cwd = os.path.join(model_dir, cwd)
                if os.path.exists(cwd): continue
                os.makedirs(cwd, exist_ok=True)
                
                # write experiment-specfic dataset
                cp(data_path, cwd, level, model)  # create symlink copy of the original
                exp_val = val.get_variant(level, mode, label)
                exp_train_val = train_val.get_variant(level, mode, label)
                write_dataset(cwd, experiment, exp_val, exp_train_val, level)  # overwrite training data with data from variant
                
                subprocess.run(f'python {REPOSITORY_ROOT}/src/{model_cmd[model]}.py -d {cwd} -i 1'.split())
                # comment aove and uncomment below to use specific GPU for BLSTM model
                # with tf.device('/gpu:1'):
                #     main(argparse.Namespace(**{'dataset':cwd, 'iters':1}))
                clean_interim_data(cwd)
                clean_weights(cwd)
