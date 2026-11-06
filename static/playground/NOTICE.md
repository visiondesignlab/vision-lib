# OpenHiggsfield integration

Model catalog and request mapping originate from [wide-trace/open-higgsfield](https://github.com/wide-trace/open-higgsfield).
The exact source commit is recorded in `catalog.json` and `mapper.js`. `scripts/sync_playground.mjs` refreshes these two files from a reviewed checkout.

The upstream repository describes itself as open source; the reviewed commit does not include a license file. This notice preserves attribution and does not assert an additional license for upstream code.

Vision Lab supplies its own interface, persistence, input validation and generation service. It is not the official Higgsfield product. The API endpoint and signed upload contract follow [Higgsfield's API documentation](https://open.higgsfield.ai/quick-start). Generation requires the visitor's own Higgsfield API key and credits.
