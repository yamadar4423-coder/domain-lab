# domain-lab

更新を停止したドメイン `dual-orbit.net` が失効するまでを定点観測した記録。

- 公開ページ: <https://yamadar4423-coder.github.io/domain-lab/>
- 観測対象: RDAP（登録情報）/ DNS レコード / HTTP 応答
- 取得方法: 認証不要の公開情報のみ。ログインも API キーも使用していない

ドメインは 2026-05-03 に取得し、2027-05-03 の失効をもって手放す。
その過程でレジストリのステータスがどう変化するかを記録している。

## 自動観測

毎月1日 03:00 UTC に GitHub Actions が `probe.py` を実行し、観測を1件追記して
公開ページを再生成する（`.github/workflows/observe.yml`）。人の操作は不要。

- `probe.py` … 観測して `data/observations.jsonl` に追記し、`OBSERVATIONS.md` を再生成
- `build_site.py` … 観測データから `index.html` を生成

手元で試す場合は引数なしで `python probe.py`。外部ライブラリは使わない。
