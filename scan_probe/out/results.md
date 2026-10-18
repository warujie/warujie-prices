# Card scan probe: results

Index: 68672 entries (33785 cards). Test photos: 2500 cards × 3 levels × 3 ways of finding the card. Run took 98.4 min.

## Best scoring per way of finding the card

| Finding | Scoring | Right card first | In top 5 | Sure (≤0.2% wrong) | Sure (≤0.5% wrong) | Sure (≤1% wrong) | Easy | Normal | Hard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| truth | h256 | 99.5% | 99.6% | 99.2% (wrong 0.0%) | 99.4% (wrong 0.0%) | 100.0% (wrong 0.3%) | 99.7% | 99.7% | 99.2% |
| detect | h256+mnv3sb | 98.0% | 98.4% | 97.1% (wrong 0.2%) | 97.4% (wrong 0.2%) | 98.5% (wrong 0.6%) | 99.5% | 99.3% | 95.3% |
| detect3 | h256+mnv3sb | 98.4% | 98.8% | 97.8% (wrong 0.1%) | 98.9% (wrong 0.4%) | 99.4% (wrong 0.9%) | 99.6% | 99.4% | 96.4% |

## Every scoring

| Finding/scoring | Right first | Top 5 | Sure ≤0.5% wrong | Easy | Normal | Hard |
| --- | --- | --- | --- | --- | --- | --- |
| truth/h256 | 99.5% | 99.6% | 99.4% | 99.7% | 99.7% | 99.2% |
| truth/h256+mnv3sb | 99.4% | 99.5% | 99.4% | 99.7% | 99.7% | 98.7% |
| truth/h256+mnv3s | 98.5% | 98.9% | 98.6% | 99.7% | 99.6% | 96.2% |
| detect3/h256+mnv3sb | 98.4% | 98.8% | 98.9% | 99.6% | 99.4% | 96.4% |
| detect3/h256 | 98.1% | 98.4% | 97.7% | 99.4% | 98.8% | 96.3% |
| detect/h256+mnv3sb | 98.0% | 98.4% | 97.4% | 99.5% | 99.3% | 95.3% |
| detect3/h256+mnv3s | 97.6% | 98.2% | 97.7% | 99.6% | 99.4% | 93.9% |
| detect/h256+mnv3s | 97.1% | 97.7% | 96.7% | 99.6% | 99.3% | 92.4% |
| detect/h256 | 97.0% | 97.4% | 96.7% | 98.4% | 97.9% | 94.8% |
| truth/mnv3s_b256 | 81.7% | 86.0% | 71.0% | 99.0% | 93.4% | 52.7% |
| truth/mnv3s_p256 | 81.5% | 85.1% | 74.3% | 99.3% | 93.0% | 52.2% |
| detect3/mnv3s_p256 | 80.6% | 84.3% | 72.5% | 99.2% | 92.8% | 49.9% |
| detect/mnv3s_p256 | 80.3% | 84.2% | 71.7% | 99.2% | 92.0% | 49.7% |
| detect/mnv3s_b256 | 80.1% | 85.2% | 67.6% | 98.8% | 91.8% | 49.8% |
| detect3/mnv3s_b256 | 79.9% | 85.0% | 68.7% | 98.7% | 91.3% | 49.6% |

## By kind of card (truth, h256): right card first / in top 5

| Kind | Easy | Normal | Hard |
| --- | --- | --- | --- |
| back_face (n=100) | 99.0% / 100.0% | 99.0% / 100.0% | 98.0% / 98.0% |
| basic_land (n=100) | 100.0% / 100.0% | 100.0% / 100.0% | 99.0% / 99.0% |
| ja_only_art (n=150) | 100.0% / 100.0% | 100.0% / 100.0% | 100.0% / 100.0% |
| ja_same_art (n=450) | 100.0% / 100.0% | 100.0% / 100.0% | 99.6% / 99.8% |
| odd_shape (n=100) | 100.0% / 100.0% | 100.0% / 100.0% | 98.0% / 98.0% |
| old_frame (n=200) | 100.0% / 100.0% | 100.0% / 100.0% | 100.0% / 100.0% |
| random (n=1200) | 99.4% / 99.4% | 99.4% / 99.4% | 98.8% / 99.1% |
| special_frame (n=200) | 100.0% / 100.0% | 100.0% / 100.0% | 100.0% / 100.0% |

## By kind of card (detect, h256+mnv3sb): right card first / in top 5

| Kind | Easy | Normal | Hard |
| --- | --- | --- | --- |
| back_face (n=100) | 100.0% / 100.0% | 99.0% / 100.0% | 93.0% / 95.0% |
| basic_land (n=100) | 100.0% / 100.0% | 99.0% / 99.0% | 97.0% / 98.0% |
| ja_only_art (n=150) | 100.0% / 100.0% | 99.3% / 99.3% | 98.7% / 99.3% |
| ja_same_art (n=450) | 99.8% / 100.0% | 99.8% / 99.8% | 95.1% / 95.8% |
| odd_shape (n=100) | 99.0% / 100.0% | 99.0% / 99.0% | 97.0% / 97.0% |
| old_frame (n=200) | 100.0% / 100.0% | 99.5% / 99.5% | 96.0% / 96.5% |
| random (n=1200) | 99.1% / 99.1% | 99.1% / 99.2% | 95.2% / 96.2% |
| special_frame (n=200) | 100.0% / 100.0% | 100.0% / 100.0% | 92.5% / 95.5% |

## By kind of card (detect3, h256+mnv3sb): right card first / in top 5

| Kind | Easy | Normal | Hard |
| --- | --- | --- | --- |
| back_face (n=100) | 99.0% / 100.0% | 100.0% / 100.0% | 93.0% / 95.0% |
| basic_land (n=100) | 100.0% / 100.0% | 99.0% / 99.0% | 98.0% / 98.0% |
| ja_only_art (n=150) | 100.0% / 100.0% | 99.3% / 99.3% | 98.7% / 98.7% |
| ja_same_art (n=450) | 100.0% / 100.0% | 99.8% / 99.8% | 97.3% / 97.8% |
| odd_shape (n=100) | 100.0% / 100.0% | 99.0% / 100.0% | 98.0% / 98.0% |
| old_frame (n=200) | 100.0% / 100.0% | 99.0% / 99.0% | 97.5% / 98.5% |
| random (n=1200) | 99.3% / 99.4% | 99.2% / 99.3% | 96.1% / 97.0% |
| special_frame (n=200) | 99.5% / 100.0% | 100.0% / 100.0% | 93.0% / 95.0% |

## Card finder

| Level | Outline found | Median corner error (share of card width) |
| --- | --- | --- |
| easy | 100.0% | 0.2% |
| normal | 100.0% | 0.2% |
| hard | 99.8% | 0.3% |

Found outlines more than 3% off: 23.7%; with the border-expanded and second outlines, the best tried is more than 3% off for 11.2%.

Seconds per match on the runner (Python, one core): {"truth": 0.6095201333333333, "detect": 0.6244425333333334, "detect3": 1.1791945333333334}
