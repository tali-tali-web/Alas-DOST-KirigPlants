WINDOW_SIZE = 128
PREDICTION_WINDOWS = 4
SMOOTHING_ALPHA = 0.25
WIND_ON_THRESHOLD = 0.60
WIND_OFF_THRESHOLD = 0.40
CLASS_LABELS = {
    0: "Control",
    1: "Wind"
}
prediction_state = {}

from scipy.signal import butter, filtfilt
import joblib
import numpy


model = joblib.load("rf_model.joblib")
def lowpass_filter(values, cutoff=2.0, fs=32.0):

    b, a = butter(
        N=4,
        Wn=cutoff,
        btype="low",
        fs=fs
    )

    return filtfilt(b, a, values)

def normalize_window(values):

    window = numpy.asarray(values, dtype=numpy.float32)
    std = window.std()

    if std == 0:
        return window - window.mean()

    return (window - window.mean()) / std

def preprocess_window(values):
    normalized = normalize_window(values)
    return lowpass_filter(normalized)

def smooth_prediction(esp_chip_id, average_probability):

    wind_index = list(model.classes_).index(1)
    wind_probability = float(average_probability[wind_index])

    state = prediction_state.get(
        esp_chip_id,
        {
            "wind_probability": wind_probability,
            "prediction": int(model.classes_[numpy.argmax(average_probability)])
        }
    )

    smoothed_wind_probability = (
        SMOOTHING_ALPHA * wind_probability
        + (1 - SMOOTHING_ALPHA) * state["wind_probability"]
    )

    prediction = state["prediction"]

    if smoothed_wind_probability >= WIND_ON_THRESHOLD:
        prediction = 1
    elif smoothed_wind_probability <= WIND_OFF_THRESHOLD:
        prediction = 0

    prediction_state[esp_chip_id] = {
        "wind_probability": smoothed_wind_probability,
        "prediction": prediction
    }

    confidence = (
        smoothed_wind_probability
        if prediction == 1
        else 1 - smoothed_wind_probability
    )

    return prediction, confidence, smoothed_wind_probability, wind_probability