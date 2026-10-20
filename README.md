# Market Watch（GitHub Pages）
日本の信用評価損益率、米国10年国債利回り、米国政策金利の参考系列、VIX、TQQQをまとめて確認する個人用ダッシュボードです。

## GitHub Pagesへの公開手順
1. GitHubで新しい **Public** リポジトリを作成（例: `market-watch`）。
2. このZIPを展開し、`index.html` と `README.md` をリポジトリのルートにアップロード。
3. リポジトリの **Settings → Pages** を開く。
4. **Build and deployment → Source** で **Deploy from a branch** を選択。
5. Branchを `main`、フォルダを `/(root)` にして **Save**。
6. 公開が完了すると `https://あなたのユーザー名.github.io/market-watch/` で閲覧できます。

## データの扱い
- 信用評価損益率: 日経225.jpのページへのリンク。自動値取得ではありません。
- 米国10年金利: FREDの `DGS10` チャートを埋め込み。
- 政策金利: FREDの `FEDFUNDS` チャートを埋め込み。これは実効FF金利の月次系列で、FOMCの目標レンジとは異なります。
- VIX、TQQQ: TradingViewのチャートウィジェットを埋め込み。
- それぞれのリンクから提供元の最新情報・定義を確認できます。

## 注意
GitHub Pagesは静的ホスティングです。外部サービスの表示・更新頻度・埋め込み許可に依存します。Publicリポジトリと公開サイトは誰でも閲覧できます。投資判断の唯一の根拠にしないでください。
