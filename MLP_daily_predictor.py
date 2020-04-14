from pathlib import Path
from finta import TA
import pandas as pd
import numpy as np
import joblib

from alpha_vantage_api import get_data


def get_model(symbol):
    model_path = Path() / "models" / f'{symbol}_model.joblib'
    if model_path.exists():
        return joblib.load(model_path)
    else:
        raise FileExistsError(f"No model exists in model directory for {symbol}")


class MLPModel():
    def __init__(self, symbol, finta_param):
        self.clf = get_model(symbol)
        self.finta_param = finta_param

    def predict(self, df):
        features = self._compute_indicators(df)
        pred = self.clf.predict(features)
        return pred

    def _compute_indicators(self, df):
        ohlc = df[["date", "open", "high", "low", "close"]]
        ohlc.set_index('date', inplace=True)

        ohlcv = df[["date", "open", "high", "low", "close", "volume"]]
        ohlcv.set_index('date', inplace=True)

        # ================================ FEATURES PREPARATION ================================

        # ---- EXPONENTIAL SMOOTHING
        # Smoothing coefficient between [0,1]
        alpha = 0.01  # past count for a third of the current value

        # stocks = stocks.drop(['date'],1)
        exp_ohlc = ohlc[:1]

        for i in range(1, len(ohlc)):
            # TODO optimized the treatment by processing with np.array
            # complete formula :  exp_stocks[i] = alpha * stocks[i:i+1] + (1-alpha) * exp_stocks[i-1:i]
            temp = (alpha * ohlc[i:i + 1]).reset_index(drop=True)
            temp = temp.add(((1 - alpha) * exp_ohlc[i - 1:i]).reset_index(drop=True), 1, fill_value=0)
            temp.index = [i]
            exp_ohlc = exp_ohlc.append(temp)

        # ---- FEATURES COMPUTATION

        # Stochastic Oscillator
        stoch_osc = TA.STOCH(ohlc, period=self.finta_param)
        # Williams %R
        will = TA.WILLIAMS(ohlc, period=self.finta_param)

        # Differenciate Close values
        diff = ohlc.diff()
        diff = diff.rename(columns={c: f"{c}_diff" for c in diff.columns})

        # diff^2
        diff2 = diff.diff()
        diff2 = diff2.rename(columns={c: f"{c}2" for c in diff.columns})

        # close diff, close diff2, will, stoch, open diff
        df_features = pd.concat([will, stoch_osc], axis=1, sort=True).join(diff[['close_diff', 'open_diff']]).join(
            diff2['close_diff2'])
        features = np.array(df_features.iloc[-1])
        return [features]


if __name__ == '__main__':
    s = 'aapl'
    # clf = get_model(s)
    """
    df columns are : 
        
    """
    df, _ = get_data(s, mode='last')
    df.rename(columns=['symbol', 'open', 'high', 'low', 'price',
                       'volume', 'date', 'previous close',
                       'change', 'change percent'])
