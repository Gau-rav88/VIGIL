from __future__ import annotations

import collections
import hashlib
import time
from typing import Any


class MinHashLSH:
    def __init__(
        self,
        num_perm: int = 128,
        shingle_len: int = 5,
        threshold: float = 0.8,
        sliding_window_s: float = 300.0,
    ) -> None:
        self.num_perm = num_perm
        self.shingle_len = shingle_len
        self.threshold = threshold
        self.sliding_window_s = sliding_window_s

        # Generate deterministic hash coefficients: (a, b)
        self.prime = 2147483647  # 2^31 - 1
        self.a_coeffs = [
            (i * 10007 + 3) % self.prime for i in range(1, num_perm + 1)
        ]
        self.b_coeffs = [
            (i * 20011 + 7) % self.prime for i in range(1, num_perm + 1)
        ]

        # LSH parameters: 16 bands x 8 rows = 128
        self.bands = 16
        self.rows_per_band = num_perm // self.bands

        # Storage:
        # band_idx -> bucket_hash -> list of msg_id
        self.lsh_buckets: list[dict[int, list[str]]] = [
            collections.defaultdict(list) for _ in range(self.bands)
        ]
        # msg_id -> {ts, signature, text_shingles, cluster_id, author_id, channel_id}
        self.records: dict[str, dict[str, Any]] = {}
        # cluster_id -> dict of cluster info
        self.clusters: dict[str, dict[str, Any]] = {}

    def _get_shingles(self, text: str) -> set[int]:
        cleaned = "".join(text.lower().split())
        if len(cleaned) < self.shingle_len:
            return {hash(cleaned) & 0x7FFFFFFF}
        shingles = set()
        for i in range(len(cleaned) - self.shingle_len + 1):
            s = cleaned[i : i + self.shingle_len]
            # 31-bit positive hash
            shingles.add(int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16) & 0x7FFFFFFF)
        return shingles

    def _compute_minhash(self, shingles: set[int]) -> list[int]:
        sig = []
        for a, b in zip(self.a_coeffs, self.b_coeffs, strict=True):
            min_val = self.prime
            for sh in shingles:
                val = (a * sh + b) % self.prime
                if val < min_val:
                    min_val = val
            sig.append(min_val)
        return sig

    def _jaccard(self, sig1: list[int], sig2: list[int]) -> float:
        matches = sum(1 for x, y in zip(sig1, sig2, strict=True) if x == y)
        return matches / len(sig1)

    def purge_expired(self, current_ts: float) -> None:
        if self.records and any(r["ts"] > (current_ts + 60.0) for r in self.records.values()):
            self.records.clear()
            self.clusters.clear()
            for b in self.lsh_buckets:
                b.clear()
            return

        cutoff = current_ts - self.sliding_window_s
        expired_ids = [
            mid for mid, r in self.records.items() if r["ts"] < cutoff
        ]
        for mid in expired_ids:
            rec = self.records.pop(mid, None)
            if not rec:
                continue
            # Remove from buckets
            sig = rec["signature"]
            for band_idx in range(self.bands):
                r_start = band_idx * self.rows_per_band
                band_slice = tuple(sig[r_start : r_start + self.rows_per_band])
                bucket_key = hash(band_slice)
                bucket = self.lsh_buckets[band_idx].get(bucket_key)
                if bucket and mid in bucket:
                    bucket.remove(mid)
                    if not bucket:
                        self.lsh_buckets[band_idx].pop(bucket_key, None)

    def insert_and_cluster(
        self,
        msg_id: str,
        text: str,
        author_id: str,
        channel_id: str,
        ts: float | None = None,
    ) -> tuple[str | None, int]:
        """
        Inserts message into sliding LSH index.
        Returns (cluster_id, cluster_size).
        If no duplicate cluster exists (size 1), cluster_id may be None.
        """
        now = ts if ts is not None else time.time()
        self.purge_expired(now)

        shingles = self._get_shingles(text)
        sig = self._compute_minhash(shingles)

        # Find candidates via LSH bands
        candidates: set[str] = set()
        for band_idx in range(self.bands):
            r_start = band_idx * self.rows_per_band
            band_slice = tuple(sig[r_start : r_start + self.rows_per_band])
            bucket_key = hash(band_slice)
            for cand_id in self.lsh_buckets[band_idx].get(bucket_key, []):
                if cand_id != msg_id:
                    candidates.add(cand_id)

        # Check candidate similarity
        matched_cluster_id: str | None = None
        for cand_id in candidates:
            cand_rec = self.records.get(cand_id)
            if not cand_rec:
                continue
            sim = self._jaccard(sig, cand_rec["signature"])
            if sim >= self.threshold:
                matched_cluster_id = cand_rec["cluster_id"]
                break

        if not matched_cluster_id:
            # New cluster
            matched_cluster_id = f"cl_{hashlib.md5(f'{msg_id}_{now}'.encode('utf-8')).hexdigest()[:12]}"
            self.clusters[matched_cluster_id] = {
                "cluster_id": matched_cluster_id,
                "first_seen": now,
                "last_seen": now,
                "message_ids": [msg_id],
                "authors": {author_id},
                "channels": {channel_id},
            }
        else:
            cl = self.clusters[matched_cluster_id]
            cl["last_seen"] = now
            cl["message_ids"].append(msg_id)
            cl["authors"].add(author_id)
            cl["channels"].add(channel_id)

        # Save record
        self.records[msg_id] = {
            "ts": now,
            "signature": sig,
            "cluster_id": matched_cluster_id,
            "author_id": author_id,
            "channel_id": channel_id,
        }

        # Insert into buckets
        for band_idx in range(self.bands):
            r_start = band_idx * self.rows_per_band
            band_slice = tuple(sig[r_start : r_start + self.rows_per_band])
            bucket_key = hash(band_slice)
            self.lsh_buckets[band_idx][bucket_key].append(msg_id)

        cluster_size = len(self.clusters[matched_cluster_id]["message_ids"])
        return matched_cluster_id, cluster_size

    def get_cluster_stats(self, cluster_id: str) -> dict[str, Any] | None:
        cl = self.clusters.get(cluster_id)
        if not cl:
            return None
        return {
            "cluster_id": cluster_id,
            "count": len(cl["message_ids"]),
            "unique_authors": len(cl["authors"]),
            "unique_channels": len(cl["channels"]),
            "duration_s": cl["last_seen"] - cl["first_seen"],
        }
