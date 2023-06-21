


def calculate_sma(data, window_size, parameter_index):
    sma = []
    for i in range(len(data)):
        if i < window_size:
            sma.append(None)  # Placeholder for SMA values before the window is filled
        else:
            window = [bar[parameter_index] for bar in data[i-window_size:i]]
            average = sum(window) / window_size
            sma.append(average)
    return sma

