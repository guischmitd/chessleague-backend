def get_expected_result(white_elo, black_elo):
    return 1 / (1 + 10 ** ((black_elo - white_elo) / 400))

def get_rating_deltas(white_elo, black_elo, outcome):
    result_mapping = {'white': (1, 0), 'black': (0, 1), 'draw': (0.5, 0.5)}
    white_score, black_score = result_mapping[outcome]

    expected_white = get_expected_result(white_elo, black_elo)

    white_delta = 32 * (white_score - expected_white)
    black_delta = 32 * (black_score - (1 - expected_white))
    return white_delta, black_delta

if __name__ == "__main__":
    from itertools import product
    w = [400, 600, 800, 1000, 1200, 1400]
    for w, b in zip(w, [1000] * len(w)):
        print(w, b)
        Ew, Eb = get_expected_result(w, b), get_expected_result(b, w)

        print(get_rating_deltas(w, b, 'draw'))