import unittest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import json
import sys
import os
import tempfile
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pre_run import StockPrerun


class TestStockPrerunParsing(unittest.TestCase):
    def setUp(self):
        self.prerun = StockPrerun(
            "data/dummy.csv",
            "config/config.json",
            "system_prompt.txt",
            "config/company_names.json",
        )

    def test_parse_option_call(self):
        result = self.prerun._parse_option('SOFI(270115C00010000)')
        self.assertIsNotNone(result)
        self.assertEqual(result['underlying'], 'SOFI')
        self.assertEqual(result['expiry'], '2027-01-15')
        self.assertEqual(result['type'], 'Call')
        self.assertEqual(result['strike'], 10.0)

    def test_parse_option_put(self):
        result = self.prerun._parse_option('AAPL(240517P00150000)')
        self.assertIsNotNone(result)
        self.assertEqual(result['underlying'], 'AAPL')
        self.assertEqual(result['expiry'], '2024-05-17')
        self.assertEqual(result['type'], 'Put')
        self.assertEqual(result['strike'], 150.0)

    def test_parse_option_invalid(self):
        result = self.prerun._parse_option('INVALID_OPTION_FORMAT')
        self.assertIsNone(result)


class TestStockPrerunPortfolio(unittest.TestCase):
    @patch('pre_run.csv.DictReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_portfolio(self, mock_file, mock_csv_reader):
        class FakeRow:
            def __init__(self, symbol, shares, cost, category):
                self.values = [symbol, shares, cost, category]
                self.idx = 0

            def get(self, key, default=None):
                v = self.values[self.idx % 4]
                self.idx += 1
                return v

        mock_csv_reader.return_value = [
            FakeRow('AAPL', '10', '150.0', 'Tech'),
            FakeRow('AAPL', '10', '160.0', 'Tech'),
            FakeRow('CASH', '1', '1000.0', ''),
            FakeRow('SOFI(270115C00010000)', '2', '1.5', 'Speculative'),
        ]

        pre = StockPrerun(
            "data/portfolio.csv",
            "config/config.json",
            "system_prompt.txt",
            "config/company_names.json",
        )
        stocks, options, cash = pre.load_portfolio()

        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0]['symbol'], 'AAPL')
        self.assertEqual(stocks[0]['shares'], 20.0)
        self.assertEqual(stocks[0]['cost_basis'], 155.0)
        self.assertEqual(cash, 1000.0)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]['underlying'], 'SOFI')
        self.assertEqual(options[0]['shares'], 2)


class TestStockPrerunConfigAndSetup(unittest.TestCase):
    def setUp(self):
        self.pre = StockPrerun(
            "data/portfolio.csv",
            "config/config.json",
            "system_prompt.txt",
            "config/company_names.json",
        )

    @patch('pre_run.os.environ.get')
    def test_check_setup_success(self, mock_env_get):
        self.pre.PORTFOLIO_FILE = MagicMock(spec=Path)
        self.pre.SYSTEM_PROMPT_FILE = MagicMock(spec=Path)
        self.pre.PORTFOLIO_FILE.exists.return_value = True
        self.pre.SYSTEM_PROMPT_FILE.exists.return_value = True
        mock_env_get.return_value = 'sk-something'
        has_key = self.pre.check_setup()
        self.assertTrue(has_key)

    @patch('pre_run.sys.exit')
    @patch('pre_run.print')
    @patch('pre_run.os.environ.get')
    def test_check_setup_failure(self, mock_env_get, mock_print, mock_exit):
        self.pre.PORTFOLIO_FILE = MagicMock(spec=Path)
        self.pre.SYSTEM_PROMPT_FILE = MagicMock(spec=Path)
        self.pre.PORTFOLIO_FILE.exists.return_value = False
        self.pre.SYSTEM_PROMPT_FILE.exists.return_value = False
        mock_env_get.return_value = None
        self.pre.check_setup()
        mock_exit.assert_called_once_with(1)

    def test_load_config_existing(self):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.exists.return_value = True
        self.pre.CONFIG_FILE.read_text.return_value = json.dumps({'model': 'custom-model'})
        config = self.pre.load_config()
        self.assertEqual(config['model'], 'custom-model')

    def test_load_config_default(self):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.exists.return_value = False
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        config = self.pre.load_config()
        self.assertEqual(config['model'], 'claude-sonnet-4-6')
        self.pre.CONFIG_FILE.write_text.assert_called_once()

    def test_load_company_names_new_format(self):
        self.pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.exists.return_value = True
        self.pre.COMPANY_NAMES_FILE.read_text.return_value = json.dumps({
            'holdings': {'AAPL': 'Apple'},
            'competitors': {'MSFT': 'Microsoft'}
        })
        names = self.pre.load_company_names()
        self.assertEqual(names['AAPL'], 'Apple')
        self.assertEqual(names['MSFT'], 'Microsoft')

    def test_save_company_names(self):
        self.pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.parent = MagicMock(spec=Path)
        names = {'AAPL': 'Apple', 'MSFT': 'Microsoft'}
        self.pre.save_company_names(names, {'AAPL'})
        self.pre.COMPANY_NAMES_FILE.write_text.assert_called_once()
        written = self.pre.COMPANY_NAMES_FILE.write_text.call_args[0][0]
        data = json.loads(written)
        self.assertIn('AAPL', data['holdings'])
        self.assertIn('MSFT', data['competitors'])

    @patch('pre_run.time.sleep')
    @patch('pre_run.yf.Ticker')
    def test_ensure_competitor_names(self, mock_ticker, mock_sleep):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = True
        comp_path.read_text.return_value = json.dumps({'holdings': {'AAPL': ['MSFT', 'GOOG']}})

        def _ticker_side_effect(sym):
            t = MagicMock()
            t.info = {'shortName': f'{sym} Inc.'}
            return t

        mock_ticker.side_effect = _ticker_side_effect
        with patch.object(self.pre, 'save_company_names') as mock_save:
            company_names = {'AAPL': 'Apple'}
            self.pre.ensure_competitor_names(company_names, {'AAPL'})
            self.assertIn('MSFT', company_names)
            self.assertIn('GOOG', company_names)
            mock_save.assert_called()

    @patch('pre_run.time.sleep')
    @patch('pre_run.requests.get')
    @patch('pre_run.os.environ.get')
    def test_auto_populate_competitors(self, mock_env_get, mock_requests_get, mock_sleep):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = False
        mock_env_get.return_value = 'mock-key'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ['MSFT', 'GOOG']
        mock_requests_get.return_value = mock_resp
        self.pre.auto_populate_competitors({'AAPL'})
        comp_path.write_text.assert_called()
        written = comp_path.write_text.call_args[0][0]
        data = json.loads(written)
        self.assertIn('AAPL', data['holdings'])
        self.assertEqual(data['holdings']['AAPL'], ['MSFT', 'GOOG'])

    @patch('pre_run.time.sleep')
    @patch('pre_run.requests.get')
    @patch('pre_run.os.environ.get')
    def test_auto_populate_competitors_filters_non_us_or_dot_ticker(self, mock_env_get, mock_requests_get, mock_sleep):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = False
        mock_env_get.return_value = 'mock-key'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ['MSFT', 'BHP.AX', '0700.HK', 'SHOP.TO', 'RDSA', 'NVDA']
        mock_requests_get.return_value = mock_resp

        self.pre.auto_populate_competitors({'AAPL'})
        written = comp_path.write_text.call_args[0][0]
        data = json.loads(written)
        self.assertEqual(data['holdings']['AAPL'], ['MSFT', 'RDSA', 'NVDA'])

    @patch('pre_run.time.sleep')
    @patch('pre_run.requests.get')
    @patch('pre_run.os.environ.get')
    def test_auto_populate_competitors_records_competitors_of_competitors(self, mock_env_get, mock_requests_get, mock_sleep):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = False
        mock_env_get.return_value = 'mock-key'

        def _resp_for(symbol):
            r = MagicMock()
            r.status_code = 200
            if symbol == 'AAPL':
                r.json.return_value = ['MSFT']
            elif symbol == 'MSFT':
                r.json.return_value = ['GOOG', 'AAPL']
            elif symbol == 'GOOG':
                r.json.return_value = []
            else:
                r.json.return_value = []
            return r

        def _get_side_effect(*args, **kwargs):
            return _resp_for(kwargs.get('params', {}).get('symbol'))

        mock_requests_get.side_effect = _get_side_effect

        self.pre.auto_populate_competitors({'AAPL'})
        written = comp_path.write_text.call_args[0][0]
        data = json.loads(written)
        self.assertEqual(data['holdings']['AAPL'], ['MSFT'])
        self.assertEqual(data['competitors']['MSFT'], [])
        self.assertNotIn('GOOG', data['competitors'])
        self.assertEqual(mock_requests_get.call_count, 1)


class TestStockPrerunBranchCoverage(unittest.TestCase):
    def setUp(self):
        self.pre = StockPrerun(
            "data/portfolio.csv",
            "config/config.json",
            "system_prompt.txt",
            "config/company_names.json",
        )

    def test_load_company_names_old_format_and_invalid_json(self):
        self.pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.exists.return_value = True
        self.pre.COMPANY_NAMES_FILE.read_text.return_value = json.dumps({'TSLA': 'Tesla'})
        names = self.pre.load_company_names()
        self.assertEqual(names['TSLA'], 'Tesla')

        self.pre.COMPANY_NAMES_FILE.read_text.return_value = '{bad-json'
        names2 = self.pre.load_company_names()
        self.assertEqual(names2, {})

    def test_save_company_names_with_existing_holdings(self):
        self.pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.parent = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.exists.return_value = True
        self.pre.COMPANY_NAMES_FILE.read_text.return_value = json.dumps({'holdings': {'AAPL': 'Apple'}})
        self.pre.save_company_names({'AAPL': 'Apple', 'MSFT': 'Microsoft'}, portfolio_symbols=None)
        payload = self.pre.COMPANY_NAMES_FILE.write_text.call_args[0][0]
        data = json.loads(payload)
        self.assertIn('AAPL', data['holdings'])
        self.assertIn('MSFT', data['competitors'])

    @patch('pre_run.os.environ.get', return_value=None)
    def test_auto_populate_competitors_no_change(self, mock_env):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = True
        comp_path.read_text.return_value = json.dumps({'holdings': {'AAPL': []}, 'competitors': {}})
        self.pre.auto_populate_competitors({'AAPL'})
        comp_path.write_text.assert_not_called()

    @patch('pre_run.os.environ.get', return_value=None)
    def test_auto_populate_competitors_removed_symbols(self, mock_env):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = True
        comp_path.read_text.return_value = json.dumps({
            'holdings': {'AAPL': ['MSFT']},
            'competitors': {'OLD': ['ZZZ']}
        })
        self.pre.auto_populate_competitors({'AAPL'})
        comp_path.write_text.assert_called()

    def test_ensure_competitor_names_early_return_branches(self):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path

        comp_path.exists.return_value = False
        self.pre.ensure_competitor_names({})

        comp_path.exists.return_value = True
        comp_path.read_text.return_value = '{bad-json'
        self.pre.ensure_competitor_names({})

        comp_path.read_text.return_value = json.dumps({'holdings': {'AAPL': ['MSFT']}})
        # missing list empty => return at line 230
        self.pre.ensure_competitor_names({'MSFT': 'Microsoft'}, {'AAPL'})

    @patch('pre_run.sys.argv', ['stock_assistant.py', '--fresh'])
    def test_process_cache_fresh_already_done(self):
        self.pre.cache_mgr = MagicMock()
        self.pre.comp_cache_mgr = MagicMock()
        self.pre.cache_mgr.has_fresh_today.return_value = True
        self.pre.cache_mgr.is_earnings_season.return_value = False
        self.pre.process_cache()
        self.pre.cache_mgr.clear.assert_not_called()
        self.pre.comp_cache_mgr.clear.assert_not_called()

    @patch('pre_run.sys.argv', ['stock_assistant.py', '--fresh'])
    def test_process_cache_fresh_clear(self):
        self.pre.cache_mgr = MagicMock()
        self.pre.comp_cache_mgr = MagicMock()
        self.pre.cache_mgr.has_fresh_today.return_value = False
        self.pre.cache_mgr.is_earnings_season.return_value = True
        self.pre.process_cache()
        self.pre.cache_mgr.clear.assert_any_call(category='news')
        self.pre.cache_mgr.clear.assert_any_call(category='technical')
        self.pre.comp_cache_mgr.clear.assert_any_call(category='news')
        self.pre.comp_cache_mgr.clear.assert_any_call(category='technical')

    @patch('pre_run.sys.argv', ['stock_assistant.py'])
    def test_process_cache_normal_mode(self):
        self.pre.cache_mgr = MagicMock()
        self.pre.comp_cache_mgr = MagicMock()
        self.pre.cache_mgr.clear_expired.return_value = 0
        self.pre.comp_cache_mgr.clear_expired.return_value = 0
        self.pre.cache_mgr.is_earnings_season.return_value = False
        self.pre.process_cache()
        self.pre.cache_mgr.clear_expired.assert_called_once()
        self.pre.comp_cache_mgr.clear_expired.assert_called_once()

    def test_save_company_names_no_existing_file_uses_all_names(self):
        self.pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.parent = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.exists.return_value = False
        self.pre.save_company_names({'AAPL': 'Apple', 'MSFT': 'Microsoft'}, portfolio_symbols=None)
        payload = self.pre.COMPANY_NAMES_FILE.write_text.call_args[0][0]
        data = json.loads(payload)
        self.assertIn('AAPL', data['holdings'])
        self.assertIn('MSFT', data['holdings'])

    def test_save_company_names_existing_read_error_fallback(self):
        self.pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.parent = MagicMock(spec=Path)
        self.pre.COMPANY_NAMES_FILE.exists.return_value = True
        self.pre.COMPANY_NAMES_FILE.read_text.side_effect = RuntimeError("boom")
        self.pre.save_company_names({'AAPL': 'Apple'}, portfolio_symbols=None)
        payload = self.pre.COMPANY_NAMES_FILE.write_text.call_args[0][0]
        data = json.loads(payload)
        self.assertIn('AAPL', data['holdings'])

    @patch('pre_run.os.environ.get', return_value='mock-key')
    @patch('pre_run.requests.get')
    @patch('pre_run.time.sleep')
    def test_auto_populate_competitors_old_format_and_empty_list(self, mock_sleep, mock_get, mock_env):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = True
        # old format => triggers 124-126 conversion path
        comp_path.read_text.return_value = json.dumps({'AAPL': []})
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        mock_get.return_value = resp
        self.pre.auto_populate_competitors({'AAPL'})
        # no peers from API still writes because changed=True in this branch
        comp_path.write_text.assert_called()

    @patch('pre_run.os.environ.get', return_value='mock-key')
    @patch('pre_run.requests.get', side_effect=RuntimeError("api down"))
    @patch('pre_run.time.sleep')
    def test_auto_populate_competitors_api_exception_branch(self, mock_sleep, mock_get, mock_env):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = False
        self.pre.auto_populate_competitors({'AAPL'})
        comp_path.write_text.assert_not_called()

    def test_auto_populate_competitors_json_load_error(self):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = True
        comp_path.read_text.side_effect = RuntimeError("bad read")
        with patch('pre_run.os.environ.get', return_value=None):
            self.pre.auto_populate_competitors({'AAPL'})
        comp_path.write_text.assert_not_called()

    @patch('pre_run.time.sleep')
    @patch('pre_run.yf.Ticker')
    def test_ensure_competitor_names_old_format_and_name_missing_and_exception(self, mock_ticker, mock_sleep):
        self.pre.CONFIG_FILE = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent = MagicMock(spec=Path)
        comp_path = MagicMock(spec=Path)
        self.pre.CONFIG_FILE.parent.__truediv__.return_value = comp_path
        comp_path.exists.return_value = True
        # old format map (hits line 218)
        comp_path.read_text.return_value = json.dumps({'AAPL': ['MSFT', 'ERR']})

        def ticker_side_effect(sym):
            if sym == 'ERR':
                raise RuntimeError("yf err")
            t = MagicMock()
            # MSFT has no short/long name => hits line 244 path
            t.info = {}
            return t

        mock_ticker.side_effect = ticker_side_effect
        with patch.object(self.pre, 'save_company_names') as mock_save:
            self.pre.ensure_competitor_names({'AAPL': 'Apple'}, {'AAPL'})
            mock_save.assert_not_called()

    @patch('pre_run.csv.DictReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_portfolio_invalid_row_empty_symbol_negative_total_and_category_fill(self, mock_file, mock_csv_reader):
        class FakeRow:
            def __init__(self, symbol, shares, cost, category):
                self.values = [symbol, shares, cost, category]
                self.idx = 0

            def get(self, key, default=None):
                v = self.values[self.idx % 4]
                self.idx += 1
                return v

        mock_csv_reader.return_value = [
            FakeRow('AAPL', '5', '100', ''),          # initial empty category
            FakeRow('AAPL', '-5', '120', 'Tech'),     # total_shares==0 -> weighted=cost path + fill category
            FakeRow('', '1', '10', 'X'),              # empty symbol branch
            FakeRow('MSFT', 'x', '10', 'Tech'),       # ValueError branch
        ]
        stocks, options, cash = self.pre.load_portfolio()
        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0]['symbol'], 'AAPL')
        self.assertEqual(stocks[0]['cost_basis'], 120.0)
        self.assertEqual(stocks[0]['category'], 'Tech')

    @patch('pre_run.sys.argv', ['stock_assistant.py'])
    def test_process_cache_normal_mode_with_removed(self):
        self.pre.cache_mgr = MagicMock()
        self.pre.comp_cache_mgr = MagicMock()
        self.pre.cache_mgr.clear_expired.return_value = 1
        self.pre.comp_cache_mgr.clear_expired.return_value = 2
        self.pre.cache_mgr.is_earnings_season.return_value = False
        self.pre.process_cache()
        self.pre.cache_mgr.clear_expired.assert_called_once()
        self.pre.comp_cache_mgr.clear_expired.assert_called_once()


class TestCompetitorSkipRegistry(unittest.TestCase):
    @patch('pre_run.time.sleep')
    @patch('pre_run.requests.get')
    @patch('pre_run.os.environ.get', return_value='mock-key')
    def test_add_skip_and_skip_next_load(self, mock_env, mock_get, mock_sleep):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cfg_dir = base / 'config'
            cfg_dir.mkdir(parents=True, exist_ok=True)
            competitors_path = cfg_dir / 'competitors.json'
            competitors_path.write_text(
                json.dumps({'holdings': {'AAPL': []}, 'competitors': {}}, ensure_ascii=False),
                encoding='utf-8',
            )

            pre = StockPrerun(
                str(base / 'portfolio.csv'),
                str(cfg_dir / 'config.json'),
                str(base / 'system_prompt.txt'),
                str(cfg_dir / 'company_names.json'),
            )

            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = []
            mock_get.return_value = resp

            pre.auto_populate_competitors({'AAPL'})

            skip_path = cfg_dir / 'competitor_skip.json'
            self.assertTrue(skip_path.exists())
            skip_data = json.loads(skip_path.read_text(encoding='utf-8'))
            self.assertIn('AAPL', skip_data.get('symbols', {}))
            self.assertEqual(
                skip_data['symbols']['AAPL'].get('reason'),
                'no_peers_or_non_us',
            )
            self.assertEqual(mock_get.call_count, 1)

            mock_get.reset_mock()
            pre.auto_populate_competitors({'AAPL'})
            mock_get.assert_not_called()

    @patch('pre_run.time.sleep')
    @patch('pre_run.os.environ.get', return_value=None)
    def test_prune_skip_older_than_90_days(self, mock_env, mock_sleep):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cfg_dir = base / 'config'
            cfg_dir.mkdir(parents=True, exist_ok=True)
            competitors_path = cfg_dir / 'competitors.json'
            competitors_path.write_text(
                json.dumps({'holdings': {'AAPL': ['MSFT']}, 'competitors': {}}, ensure_ascii=False),
                encoding='utf-8',
            )

            today = datetime.date.today()
            old_date = (today - datetime.timedelta(days=91)).isoformat()
            new_date = (today - datetime.timedelta(days=10)).isoformat()
            skip_path = cfg_dir / 'competitor_skip.json'
            skip_path.write_text(
                json.dumps({
                    "_schema_version": "1.0",
                    "symbols": {
                        "OLD": {"added_at": old_date, "reason": "no_peers_or_non_us"},
                        "NEW": {"added_at": new_date, "reason": "no_peers_or_non_us"},
                    },
                }, ensure_ascii=False),
                encoding='utf-8',
            )

            pre = StockPrerun(
                str(base / 'portfolio.csv'),
                str(cfg_dir / 'config.json'),
                str(base / 'system_prompt.txt'),
                str(cfg_dir / 'company_names.json'),
            )

            pre.auto_populate_competitors({'AAPL'})
            updated = json.loads(skip_path.read_text(encoding='utf-8'))
            self.assertNotIn('OLD', updated.get('symbols', {}))
            self.assertIn('NEW', updated.get('symbols', {}))


class TestStockPrerunCoverageExtra(unittest.TestCase):
    def _new_pre(self):
        return StockPrerun(
            "data/portfolio.csv",
            "config/config.json",
            "system_prompt.txt",
            "config/company_names.json",
        )

    def test_peer_symbol_and_normalize_extra(self):
        self.assertFalse(StockPrerun._is_us_peer_symbol(123))
        out = StockPrerun._normalize_peer_list(["AAPL", 1, "AAPL.B", "msft"], "AAPL")
        self.assertEqual(out, ["MSFT"])

    def test_prune_skip_registry_invalid_date(self):
        pre = self._new_pre()
        data = {"symbols": {"AAPL": {"added_at": "bad-date"}}}
        self.assertFalse(pre._prune_skip_registry(data))

    def test_load_config_read_error(self):
        pre = self._new_pre()
        pre.CONFIG_FILE = MagicMock(spec=Path)
        pre.CONFIG_FILE.exists.return_value = True
        pre.CONFIG_FILE.read_text.side_effect = RuntimeError("boom")
        cfg = pre.load_config()
        self.assertIn("model", cfg)

    def test_load_company_names_non_dict_and_save_merge(self):
        pre = self._new_pre()
        pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        pre.COMPANY_NAMES_FILE.exists.return_value = True
        pre.COMPANY_NAMES_FILE.read_text.return_value = json.dumps(["bad"])
        self.assertEqual(pre.load_company_names(), {})

        pre.COMPANY_NAMES_FILE.read_text.return_value = json.dumps({"AAPL": "Apple", "MSFT": "Microsoft"})
        pre.save_company_names({"AAPL": "Apple", "NVDA": "NVIDIA"}, portfolio_symbols=None)
        payload = json.loads(pre.COMPANY_NAMES_FILE.write_text.call_args[0][0])
        self.assertIn("AAPL", payload["holdings"])
        self.assertIn("NVDA", payload["competitors"])

    def test_save_company_names_preserve_existing_competitor(self):
        pre = self._new_pre()
        pre.COMPANY_NAMES_FILE = MagicMock(spec=Path)
        pre.COMPANY_NAMES_FILE.exists.return_value = True
        pre.COMPANY_NAMES_FILE.read_text.return_value = json.dumps(
            {"holdings": {"AAPL": "Apple"}, "competitors": {"MSFT": "Microsoft"}}
        )
        pre.save_company_names({"AAPL": "Apple"}, {"AAPL"})
        payload = json.loads(pre.COMPANY_NAMES_FILE.write_text.call_args[0][0])
        self.assertIn("MSFT", payload["competitors"])

    @patch("pre_run.requests.get")
    @patch("pre_run.os.environ.get", return_value="k")
    @patch("pre_run.time.sleep")
    def test_auto_populate_filters_and_status_cleanup(self, _sleep, _env, mock_get):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cfg_dir = base / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            comp = cfg_dir / "competitors.json"
            comp.write_text(
                json.dumps(
                    {
                        "holdings": {"AAPL": ["MSFT"], "BAD.1": ["ZZZ"]},
                        "competitors": {"AAPL": ["TSLA"], "MSFT": ["AAPL"]},
                    }
                ),
                encoding="utf-8",
            )
            pre = StockPrerun(str(base / "p.csv"), str(cfg_dir / "config.json"), str(base / "s.txt"), str(cfg_dir / "c.json"))
            resp = MagicMock()
            resp.status_code = 500
            mock_get.return_value = resp
            pre.auto_populate_competitors({"AAPL"})
            data = json.loads(comp.read_text(encoding="utf-8"))
            self.assertIn("AAPL", data["holdings"])

    @patch("pre_run.requests.get")
    @patch("pre_run.os.environ.get", return_value="k")
    @patch("pre_run.time.sleep")
    def test_auto_populate_fetches_candidate_roots_only(self, _sleep, _env, mock_get):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cfg_dir = base / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "competitors.json").write_text(
                json.dumps({"holdings": {"AAPL": []}, "competitors": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (cfg_dir / "candidates.txt").write_text("TSLA\n", encoding="utf-8")

            def _resp_for(symbol):
                r = MagicMock()
                r.status_code = 200
                if symbol == "TSLA":
                    r.json.return_value = ["MSFT"]
                else:
                    r.json.return_value = []
                return r

            mock_get.side_effect = lambda *args, **kwargs: _resp_for(kwargs.get("params", {}).get("symbol"))
            pre = StockPrerun(str(base / "p.csv"), str(cfg_dir / "config.json"), str(base / "s.txt"), str(cfg_dir / "c.json"))
            pre.auto_populate_competitors({"AAPL"})
            data = json.loads((cfg_dir / "competitors.json").read_text(encoding="utf-8"))
            self.assertIn("TSLA", data.get("competitors", {}))
            self.assertNotIn("MSFT", data.get("competitors", {}))

    def test_process_cache_no_mgr(self):
        pre = self._new_pre()
        pre.cache_mgr = None
        pre.comp_cache_mgr = None
        pre.process_cache()

    @patch("pre_run.os.environ.get", return_value=None)
    @patch("pre_run.time.sleep")
    def test_auto_populate_cleanup_and_none_to_empty(self, _sleep, _env):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cfg_dir = base / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            comp = cfg_dir / "competitors.json"
            comp.write_text(
                json.dumps(
                    {
                        "holdings": {"AAPL": None, "MSFT": ["AAPL"]},
                        "competitors": {"BAD.1": ["AAPL"]},
                    }
                ),
                encoding="utf-8",
            )
            pre = StockPrerun(str(base / "p.csv"), str(cfg_dir / "config.json"), str(base / "s.txt"), str(cfg_dir / "c.json"))
            pre.auto_populate_competitors({"AAPL"})
            data = json.loads(comp.read_text(encoding="utf-8"))
            self.assertNotIn("MSFT", data["holdings"])
            self.assertNotIn("BAD.1", data["competitors"])
            self.assertEqual(data["holdings"]["AAPL"], [])


if __name__ == '__main__':
    unittest.main()
