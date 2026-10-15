from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.features import engineer, feature_columns


def similar_listings(df: pd.DataFrame, listing_idx: int, k: int = 5) -> pd.DataFrame:
    """Return k nearest listings (excluding itself) in engineered feature space."""
    if len(df) < 2:
        return df.iloc[0:0]
    engineered = engineer(df)
    nums, cats = feature_columns()
    pipe = Pipeline(
        [
            (
                "prep",
                ColumnTransformer(
                    [
                        ("num", StandardScaler(), nums),
                        ("cat", OneHotEncoder(handle_unknown="ignore"), cats),
                    ]
                ),
            ),
            ("nn", NearestNeighbors(n_neighbors=min(k + 1, len(engineered)), metric="euclidean")),
        ]
    )
    pipe.fit(engineered[nums + cats])
    nn = pipe.named_steps["nn"]
    xt = pipe.named_steps["prep"].transform(engineered[nums + cats])
    distances, indices = nn.kneighbors(xt[listing_idx].reshape(1, -1))
    neighbors = [i for i in indices[0] if i != listing_idx][:k]
    result = df.iloc[neighbors].copy()
    result["similarity_distance"] = distances[0][1 : 1 + len(neighbors)]
    return result


def similar_by_id(df: pd.DataFrame, listing_id: str, k: int = 5) -> pd.DataFrame:
    matches = np.where(df["listing_id"].astype(str).to_numpy() == str(listing_id))[0]
    if len(matches) == 0:
        raise KeyError(listing_id)
    return similar_listings(df, int(matches[0]), k=k)
