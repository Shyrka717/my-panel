#!/bin/sh
# исходные данные: модель MPFB (CC0) и записи CMU в BVH
set -e
cd "$(dirname "$0")" && mkdir -p data/bvh
curl -fL -o data/mpfb.glb https://raw.githubusercontent.com/met4citizen/TalkingHead/main/avatars/mpfb.glb
for c in 05_02 05_11 137_23 137_24 137_37 13_14 13_29 13_39 140_06 140_07 140_08 141_12 141_13 141_16 141_18 141_20 141_21 141_22 141_26 143_06 143_25 143_34 143_35 16_01 16_35 35_17 35_18 49_09 60_01 60_02 61_01 61_02 79_16 79_69 80_06 80_14 80_48 90_30 90_31 90_32 91_29 91_54 91_60 93_03 93_04 93_06 93_08 94_01 94_02 94_05 141_16; do
  s=${c%%_*}; s3=$(printf "%03d" $((10#$s)))
  [ -s "data/bvh/$c.bvh" ] || curl -fL -o "data/bvh/$c.bvh" "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/$s3/$c.bvh"
done
