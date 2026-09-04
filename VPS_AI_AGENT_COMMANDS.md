# NodeTrade — VPS AI Agent Execution Commands

## TUJUAN

Dokumen ini adalah **perintah kerja untuk AI Agent yang berjalan di VPS Windows/MT5**. Jalankan pekerjaan yang tidak dapat divalidasi dari GitHub CI: koneksi MT5 nyata, pengambilan data market nyata, training/evaluasi model, compile EA `.mq5 -> .ex5`, dry-run end-to-end, dan deployment server.

**Jangan mengubah filosofi NodeTrade.** Tetap gunakan:

`Predict → Observe → Update → Execute → Recalculate`

Predictive-first, scenario/path-based, adaptive, no martingale, cost-aware, risk berdasarkan invalidation distance, dan jangan menganggap satu loss sebagai alasan untuk langsung mengubah model.

---

## ATURAN KESELAMATAN

1. **Jangan menjalankan live trading otomatis.** Pastikan `InpLiveTrading=false` sampai seluruh checklist dry-run lulus.
2. Jangan meminta, menyimpan, atau mengirim password broker ke NodeTrade server.
3. Jangan commit secret, API key, activation secret, password, token, atau credential ke GitHub.
4. Jangan menghapus dataset/model lama sebelum membuat backup.
5. Jangan overwrite production model tanpa evaluasi OOS/walk-forward yang terdokumentasi.
6. Jangan melatih model dari raw trade events tanpa validasi kualitas data.
7. Jika data tidak cukup atau kualitas buruk, **STOP dan laporkan**, jangan membuat data palsu.
8. Jangan menggunakan martingale, revenge sizing, atau menaikkan risiko setelah loss.
9. Setiap perubahan kode harus diuji dan dicatat.
10. Jika ada kegagalan broker/MT5/API, fail closed: `WAIT`, bukan memaksa order.

---

# PHASE 1 — AUDIT ENVIRONMENT

Jalankan dan catat:

- Windows version
- Python version
- pip version
- Git version
- MT5 terminal version/build
- MetaEditor version/build
- broker name
- MT5 server name
- account login ID
- account mode (netting/hedging)
- symbol XAUUSD yang sebenarnya digunakan broker
- terminal data path
- NodeTrade repository path

Jangan mencetak password/secret.

Pastikan repository NodeTrade sudah up to date dari branch `main`.

```powershell
git fetch --all
git checkout main
git pull --ff-only origin main
git status
```

---

# PHASE 2 — INSTALL & VERIFY NODETRADE

Buat virtual environment jika belum ada.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[test,server]"
pytest -q
```

Jika extra `server` belum tersedia di repository, jangan membuat dependency palsu. Baca `pyproject.toml` dan install dependency server yang memang didefinisikan.

**Kriteria:** semua automated tests PASS.

Jika gagal:
- simpan traceback
- diagnosis root cause
- perbaiki hanya jika perubahan memang diperlukan
- jalankan ulang seluruh test suite

---

# PHASE 3 — VERIFY MT5 PYTHON CONNECTION

Pastikan MT5 terminal berjalan dan akun sudah login.

Gunakan Python package `MetaTrader5`.

Verifikasi:

- `mt5.initialize()`
- `mt5.account_info()`
- `mt5.terminal_info()`
- `mt5.symbol_info(<XAUUSD symbol>)`
- `mt5.symbol_info_tick(<XAUUSD symbol>)`
- `mt5.copy_rates_from(...)`
- positions/orders/history dapat dibaca

Jangan melakukan order.

Simpan hasil non-secret ke:

`artifacts/mt5_environment_report.json`

---

# PHASE 4 — COLLECT REAL XAUUSD DATA

Ambil data historis nyata dari MT5 terminal untuk symbol broker yang benar.

Minimal target awal:

- M1: sebanyak yang tersedia dan berkualitas
- M5: sebanyak yang tersedia
- M15: sebanyak yang tersedia
- H1: sebanyak yang tersedia

Prioritaskan data historis panjang. Jangan mengarang candle.

Export ke:

`data/raw/mt5/<SYMBOL>_<TIMEFRAME>.csv`

Kolom minimum:

`time, open, high, low, close, tick_volume, spread, real_volume`

Catat:

- jumlah bar
- earliest timestamp
- latest timestamp
- duplicate timestamps
- missing timestamps
- invalid OHLC
- zero/negative prices
- abnormal spread
- missing values

---

# PHASE 5 — DATA VALIDATION

Gunakan validator NodeTrade yang sudah ada jika sesuai.

Reject data jika:

- `high < max(open, close)`
- `low > min(open, close)`
- `high < low`
- timestamp mundur
- duplicate timestamp
- harga non-positive
- spread tidak masuk akal
- data kosong/terlalu sedikit

Buat laporan:

`artifacts/data_quality_report.json`

**Penting:** jangan menghapus anomali tanpa mencatatnya. Bedakan data broker yang valid dari data corruption.

---

# PHASE 6 — TRAINING DATASET

Bangun dataset dari data market tervalidasi menggunakan feature pipeline NodeTrade.

Gunakan feature yang causal. Tidak boleh ada future leakage.

Target model tetap 3-state:

- DOWN
- FLAT
- UP

Gunakan horizon yang sudah didefinisikan NodeTrade/model. Jangan mengganti label hanya untuk memperbagus score.

Pisahkan data secara kronologis.

**DILARANG:** random train/test shuffle untuk evaluasi time-series.

Simpan metadata dataset:

`artifacts/training_dataset_manifest.json`

---

# PHASE 7 — TRAIN MODEL

Latih `CausalDirectionModel` NodeTrade pada dataset nyata.

Gunakan training period kronologis.

Lakukan:

1. baseline/base-rate comparison
2. training
3. validation
4. walk-forward/OOS
5. evaluasi per regime jika memungkinkan
6. evaluasi confusion matrix
7. evaluasi calibration/probability quality jika tersedia
8. evaluasi drawdown/trading-oriented metrics melalui backtest

Jangan menilai model hanya berdasarkan accuracy.

Minimal catat:

- sample count
- class distribution
- train period
- validation period
- OOS period
- accuracy
- balanced accuracy jika tersedia
- precision/recall per class
- confusion matrix
- probability calibration metric jika tersedia
- backtest return
- max drawdown
- trade count
- win rate
- expectancy
- profit factor jika dapat dihitung
- cost assumptions

Simpan artefak ke:

`artifacts/models/<timestamp>/`

Sertakan:

- model
- config
- feature list
- dataset hash
- training timestamp
- Git commit SHA
- metrics JSON

---

# PHASE 8 — MODEL ACCEPTANCE GATE

**Jangan memasang model sebagai production model hanya karena metric terlihat bagus.**

Model hanya boleh dipromosikan jika:

- tidak ada lookahead leakage
- OOS/walk-forward tersedia
- performa mengalahkan baseline secara bermakna
- hasil tidak hanya berasal dari satu periode/regime
- drawdown masih sesuai RiskConfig
- cost/spread/slippage sudah diperhitungkan
- jumlah trade cukup untuk evaluasi yang masuk akal
- tidak ada indikasi overfitting yang jelas

Jika tidak lulus: status `REJECTED`, jangan deploy.

Buat:

`artifacts/model_acceptance_report.json`

---

# PHASE 9 — COMPILE MT5 EA

Buka:

`integrations/mt5/NodeTradeEA.mq5`

Compile menggunakan MetaEditor yang benar-benar terpasang di VPS.

Target:

`NodeTradeEA.ex5`

Periksa compiler output.

**Kriteria wajib:**

- 0 errors
- 0 warnings jika memungkinkan
- tidak ada implicit conversion berbahaya
- tidak ada undeclared identifier
- tidak ada invalid trade API usage

Simpan hasil compiler ke:

`artifacts/mt5_compile_report.txt`

Jangan klaim `.ex5` valid sebelum compile benar-benar berhasil.

---

# PHASE 10 — MT5 WEBREQUEST CONFIGURATION

Tambahkan hanya origin NodeTrade server yang benar ke:

MT5 → Tools → Options → Expert Advisors → Allow WebRequest for listed URL

Jangan menonaktifkan seluruh security.

Pastikan HTTPS digunakan untuk server production.

---

# PHASE 11 — SERVER DEPLOYMENT

Jalankan NodeTrade API pada VPS dengan environment variables, bukan hardcoded secret.

Minimal:

- `NODETRADE_LICENSE_SECRET`
- `NODETRADE_DB`

Server harus:

- listen pada interface yang dibutuhkan
- menggunakan HTTPS melalui reverse proxy untuk production
- restart otomatis jika crash
- memiliki log rotation
- tidak menulis credential ke log

Health check:

`GET /health`

Harus berhasil.

---

# PHASE 12 — LICENSE / ACCOUNT ACTIVATION TEST

Buat test account/license non-production.

Verifikasi:

1. valid account + valid activation code → activate
2. wrong account → reject
3. wrong activation code → reject
4. expired license → reject
5. revoked/disabled license → reject
6. session bound to correct account
7. heartbeat works
8. stale/invalid session cannot trade

Jangan memasukkan activation secret ke Git.

---

# PHASE 13 — END-TO-END DRY RUN

**Live trading harus OFF.**

Pasang EA ke chart XAUUSD demo/paper environment.

Set:

`InpLiveTrading=false`

Verifikasi alur:

`MT5 EA → activate → heartbeat → market data → /v1/analyze → signal → EA receives signal`

Periksa:

- bid/ask
- spread
- equity
- day-start equity
- broker tick size
- tick value
- volume min/max/step
- stop/target
- request ID/signal ID
- action LONG/SHORT/WAIT
- scenario output
- server latency

EA harus **WAIT** jika server error, license error, data invalid, spread abnormal, atau reconciliation tidak aman.

---

# PHASE 14 — TRADE FEEDBACK TEST

Gunakan demo/paper trade hanya untuk menguji lifecycle.

Verifikasi:

- order/deal event
- `OnTradeTransaction`
- deal selection/history
- realized profit
- swap
- commission
- fee
- volume
- entry/exit
- position ID
- order ID
- event ID
- duplicate event handling

Pastikan satu event tidak menghasilkan duplicate database record.

---

# PHASE 15 — RESTART / RECONNECT TEST

Test secara nyata:

1. restart EA
2. restart MT5
3. restart NodeTrade API
4. temporarily disconnect network
5. reconnect network
6. verify session recovery
7. verify account reconciliation
8. verify existing positions are not duplicated
9. verify stale signal is not executed
10. verify server/EA returns WAIT when state is uncertain

**Tidak boleh ada order ganda akibat reconnect/restart.**

---

# PHASE 16 — RISK / BROKER RULE TEST

Verifikasi broker:

- volume min
- volume max
- volume step
- tick size
- tick value
- stops level
- freeze level
- filling mode
- market open/closed
- symbol trade mode

Uji bahwa SL/TP tidak dikirim jika melanggar broker stop/freeze rules.

Uji volume sizing dengan beberapa equity dan stop distances.

Pastikan tidak ada martingale.

---

# PHASE 17 — TRAINING FEEDBACK PIPELINE

Trade events yang masuk dari EA **tidak boleh langsung menjadi training data**.

Pipeline:

`MT5 EA → API → validation → raw storage → quality filter → staged dataset → training → walk-forward/OOS → model acceptance → registry → production`

Setiap training harus menyimpan:

- dataset hash
- source range
- Git SHA
- model version
- hyperparameters
- metrics
- acceptance decision

---

# PHASE 18 — FINAL AUDIT

Buat:

`artifacts/VPS_FINAL_AUDIT.md`

Isi tabel:

| Check | Status | Evidence |
|---|---|---|
| GitHub tests | PASS/FAIL | CI/commit |
| MT5 connection | PASS/FAIL | report |
| Real XAUUSD data | PASS/FAIL | dataset |
| Data validation | PASS/FAIL | report |
| Model training | PASS/FAIL | model artifact |
| Walk-forward OOS | PASS/FAIL | metrics |
| Model acceptance | PASS/FAIL | report |
| EA compile | PASS/FAIL | compiler log |
| API health | PASS/FAIL | health response |
| License activation | PASS/FAIL | test log |
| Dry-run signal | PASS/FAIL | logs |
| Trade feedback | PASS/FAIL | logs |
| Reconnect | PASS/FAIL | logs |
| Reconciliation | PASS/FAIL | logs |
| Broker rules | PASS/FAIL | report |
| Live trading | DISABLED | must remain disabled |

---

# FINAL RESPONSE FORMAT FOR AI AGENT

Setelah pekerjaan selesai, jangan hanya bilang “selesai”. Berikan:

1. `FINAL STATUS: READY / NOT READY`
2. Git commit SHA yang digunakan
3. jumlah bar/data per timeframe
4. training dataset size
5. model version
6. walk-forward/OOS metrics
7. model acceptance result
8. EA compiler result
9. API health result
10. dry-run result
11. reconnect/reconciliation result
12. trade feedback result
13. file/artifact locations
14. daftar blocker yang benar-benar belum dapat diselesaikan

Jika ada satu komponen kritis gagal, tulis `NOT READY`.

**JANGAN PERNAH MENYATAKAN READY HANYA KARENA TEST PYTHON PASS.**

## DEFINISI SELESAI

NodeTrade baru boleh disebut **end-to-end validated** jika:

- automated tests PASS
- data market nyata tervalidasi
- model benar-benar trained
- walk-forward/OOS lulus acceptance gate
- EA `.ex5` berhasil compile
- API hidup melalui HTTPS
- activation/license bekerja
- EA ↔ API dry-run bekerja
- trade feedback bekerja
- restart/reconnect/reconciliation bekerja
- broker execution constraints tervalidasi
- live trading tetap OFF sampai user secara eksplisit mengaktifkannya setelah semua bukti tersedia.
