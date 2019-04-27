import re
import tqdm
import argparse
import pandas as pd
from pathlib import Path

from src.predictor import Predictor
from src.audio import read_as_melspectrogram
from src.transforms import get_transforms
from src import config


parser = argparse.ArgumentParser()
parser.add_argument('--experiment', required=True, type=str)
args = parser.parse_args()


EXPERIMENT_DIR = config.experiments_dir / args.experiment
PREDICTION_DIR = config.predictions_dir / args.experiment
DEVICE = 'cuda'
CROP_SIZE = 128
BATCH_SIZE = 16


def pred_val_fold(predictor, fold):
    pass


def pred_test_fold(predictor, fold):
    subm_df = pd.read_csv(config.sample_submission)
    subm_df.set_index('fname', inplace=True)
    subm_df = subm_df.astype(float)
    assert all(subm_df.columns == config.classes)

    for fname in tqdm.tqdm(subm_df.index):
        image = read_as_melspectrogram(config.test_dir / fname)
        pred = predictor.predict(image)
        subm_df.loc[fname] = pred

    fold_prediction_dir = PREDICTION_DIR / f'fold_{fold}' / 'test'
    fold_prediction_dir.mkdir(parents=True, exist_ok=True)
    subm_df.to_csv(fold_prediction_dir / 'probs.csv')


def get_best_model_path(dir_path: Path):
    model_scores = []
    for model_path in dir_path.glob('*.pth'):
        score = re.search(r'-(\d+(?:\.\d+)?).pth', str(model_path))
        if score is not None:
            score = score.group(0)[1:-4]
            model_scores.append((model_path, score))
    model_score = sorted(model_scores, key=lambda x: x[1])
    best_model_path = model_score[-1][0]
    return best_model_path


def blend_test_predictions():
    probs_df_lst = []
    for fold in config.folds:
        fold_probs_path = PREDICTION_DIR / f'fold_{fold}' / 'test' / 'probs.csv'
        probs_df = pd.read_csv(fold_probs_path)
        probs_df.set_index('fname', inplace=True)
        probs_df_lst.append(probs_df)

    blend_df = probs_df_lst[0]
    for probs_df in probs_df_lst[1:]:
        blend_df += probs_df
    blend_df = blend_df / len(probs_df_lst)

    if config.kernel:
        blend_df.to_csv('submission.csv')
    else:
        blend_df.to_csv(PREDICTION_DIR / 'probs.csv')


if __name__ == "__main__":
    transforms = get_transforms(False, CROP_SIZE)

    for fold in config.folds:
        print("Predict fold", fold)
        fold_dir = EXPERIMENT_DIR / f'fold_{fold}'
        model_path = get_best_model_path(fold_dir)
        print("Model path", model_path)
        predictor = Predictor(model_path, transforms,
                              BATCH_SIZE, CROP_SIZE, CROP_SIZE//2,
                              device=DEVICE)

        if not config.kernel:
            print("Val predict")
            pred_val_fold(predictor, fold)

        print("Test predict")
        pred_test_fold(predictor, fold)

    print("Blend folds predictions")
    blend_test_predictions()
