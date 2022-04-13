{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 4,
   "id": "55e2262a",
   "metadata": {},
   "outputs": [],
   "source": [
    "\"\"\"\n",
    "Do-it-yourself passive socially responsible investing example algo\n",
    "Author: evan@alpaca.markets\n",
    "Notes:\n",
    "*New SRI portfolio only accurate when run during regular trading hours\n",
    "*All orders submitted are MARKET DAY orders\n",
    "*Tries to obtain thematic allocations as close as possible to desired\n",
    "*Minimum account balance you'll need to use this algo is enough to buy at least 1 share of each of your desired thematic exposures\n",
    "*Generally speaking, the allocation model works better with at least $1,000 and improves as even larger amounts are invested\n",
    "*Liquidating orders in non-thematic stocks to free up capital when necessary to fulfill the desired allocation\n",
    "are in no particular order and will liquidate the entire position before evaluating whether or not to liquidate another.\n",
    "*Algo is for illustrative purposes only and is not a recommendation to buy or sell a security.\n",
    "\"\"\"\n",
    "\n",
    "import argparse\n",
    "import math\n",
    "import alpaca_trade_api as ata\n",
    "\n",
    "SYMBOL_MAP = {'diversified':[\"Diversified SRI\",\"USSG\"],\n",
    "              'water':[\"Clean Water\",\"PHO\"],\n",
    "              'energy':[\"Renewable Energy\",\"ICLN\"],\n",
    "              'health':[\"Healthy Living\",\"BFIT\"],\n",
    "              'disease':[\"Disease Eradication\",\"XBI\"],\n",
    "              'gender':[\"Gender Diversity\",\"SHE\"]}\n",
    "\n",
    "def print_acct(positions,equity,themes):\n",
    "    print(\"Theme                | Symbol | Qty    | Market Value | % of Portfolio \")\n",
    "    print(\"-----------------------------------------------------------------------\")\n",
    "    for t in themes:\n",
    "        if t.target==0:\n",
    "            print(\"%-20s | %-6s | %-6s | %-12s | %-14s\" % (t.name, \"0\", \"0\", \"0\", \"0\"))\n",
    "        else:\n",
    "            for p in positions:\n",
    "                if t.symbol == p.symbol:\n",
    "                    print(\"%-20s | %-6s | %-6s | %-12s | %-14s\" % (t.name,p.symbol,p.qty, p.market_value, round(float(p.market_value)/float(equity)*100,2)))\n",
    "                    break\n",
    "\n",
    "class Theme():\n",
    "    def __init__(self,name,alloc,symbol,price,amount):\n",
    "        self.name = name\n",
    "        self.symbol = symbol\n",
    "        self.ref_price = price\n",
    "        self.target = alloc/100.0\n",
    "        self.shares = math.floor((amount*self.target)/self.ref_price)\n",
    "        self.value = self.shares*self.ref_price\n",
    "        self.actual = round(self.value/amount,4)\n",
    "        self.order = []\n",
    "\n",
    "\n",
    "def main(args):\n",
    "    #initialize\n",
    "    api = ata.REST(key_id='<your key id>', secret_key='<your secret key>',base_url='https://api.alpaca.markets', api_version='v2')\n",
    "    acct = api.get_account()\n",
    "    equity = float(acct.equity)\n",
    "    positions = api.list_positions()\n",
    "    if args.amount:\n",
    "        amount = int(args.amount)\n",
    "    else:\n",
    "        amount = float(equity)\n",
    "\n",
    "    print(\"\\nAmount to allocate/rebalance:\", amount)\n",
    "    print(\"Account equity:\", equity)\n",
    "\n",
    "    a_sum = 0\n",
    "    orders = []\n",
    "    themes = []\n",
    "    symbols = []\n",
    "\n",
    "    #build each theme and order\n",
    "    for arg in vars(args):\n",
    "        if arg in SYMBOL_MAP:\n",
    "            symbol = SYMBOL_MAP[arg][1]\n",
    "            symbols += [symbol]\n",
    "            name = SYMBOL_MAP[arg][0]\n",
    "            alloc = vars(args)[arg]\n",
    "            a_sum += alloc\n",
    "            bars = api.get_barset(symbol,'minute',limit=10)\n",
    "            price = bars[symbol][-1].c * 1.04\n",
    "            theme = Theme(name, alloc, symbol, price, amount)\n",
    "            #initialize order assuming no existing position\n",
    "            theme.order = [\"buy\", theme.shares, theme.symbol, theme.value]\n",
    "            themes += [theme]\n",
    "            # check existing positions to determine qty to buy/sell for rebalance\n",
    "            for p in positions:\n",
    "                if symbol == p.symbol:\n",
    "                    qty = theme.shares - int(p.qty)\n",
    "                    if qty < 0:\n",
    "                        theme.order = [\"sell\", abs(qty), theme.symbol, qty*theme.ref_price]\n",
    "                    else:\n",
    "                        theme.order = [\"buy\", qty, theme.symbol, qty*theme.ref_price]\n",
    "                    break\n",
    "            if theme.order[1]!=0:\n",
    "                orders += [theme.order]\n",
    "    assert a_sum <= 100, \"Sum of allocations exceeds 100%\"\n",
    "\n",
    "    #output current SRI state\n",
    "    print(\"\\nCurrent SRI Portfolio\")\n",
    "    print_acct(positions,equity,themes)\n",
    "\n",
    "    #generate liquidating orders in other holdings if necessary to free up cash\n",
    "    approx_value_to_buy = sum(o[3] for o in orders)\n",
    "    portfolio_value = float(acct.long_market_value) + abs(float(acct.short_market_value))\n",
    "    portfolio_avail = equity - portfolio_value\n",
    "    print(\"\\nValue of all holdings:\",portfolio_value)\n",
    "    if portfolio_avail < approx_value_to_buy:\n",
    "        deficit = round(approx_value_to_buy - portfolio_avail,2)\n",
    "        print(\"Need to free up %s to rebalance.\" %deficit)\n",
    "        for p in positions:\n",
    "            if p.symbol not in symbols:\n",
    "                print(\"\\nSubmitting liquidating orders...\")\n",
    "                if deficit>0:\n",
    "                    q = int(p.qty)\n",
    "                    if q<0:\n",
    "                        print('%s %s %s' % (\"buy\", abs(q), p.symbol))\n",
    "                        api.submit_order(symbol=p.symbol, qty=abs(q), side=\"buy\", type='market', time_in_force='day')\n",
    "                    if q>0:\n",
    "                        print('%s %s %s' % (\"sell\", q, p.symbol))\n",
    "                        api.submit_order(symbol=p.symbol, qty=q, side=\"sell\", type='market', time_in_force='day')\n",
    "                    b = api.get_barset(p.symbol, 'minute', limit=10)\n",
    "                    p = b[p.symbol][-1].c * 1.04\n",
    "                    mv = round(abs(p*q),2)\n",
    "                    deficit -= mv\n",
    "                    if deficit>0:\n",
    "                        print(\"Still need to free up %s to rebalance.\" %deficit)\n",
    "                    else:\n",
    "                        print(\"Done freeing up funds to invest.\")\n",
    "\n",
    "    #output thematic rebalance orders and final account state\n",
    "    print(\"\\nSubmitting orders...\")\n",
    "    for o in orders:\n",
    "        print('%s %s %s' %(o[0],o[1],o[2]))\n",
    "        api.submit_order(symbol=o[2], qty=o[1], side=o[0], type='market', time_in_force='day')\n",
    "    print(\"\\nNew SRI Portfolio\")\n",
    "    equity = api.get_account().equity\n",
    "    print_acct(api.list_positions(),equity,themes)\n",
    "\n",
    "#if __name__ == '__main__':\n",
    "#    parser = argparse.ArgumentParser()\n",
    "#    parser.add_argument('--amount', help='$ amount to allocate, if no value specified then uses current account equity')\n",
    "#    parser.add_argument('--diversified', type=int, help='% alloc to Diversified SRI(high ESG performance)', required=True)\n",
    "#    parser.add_argument('--water', type=int, help='% alloc to Clean Water', required=True)\n",
    "#    parser.add_argument('--energy', type=int, help='% alloc to Renewable Energy', required=True)\n",
    "#    parser.add_argument('--health', type=int, help='% alloc to Healthy Living', required=True)\n",
    "#    parser.add_argument('--disease', type=int, help='% alloc to Disease Eradication', required=True)\n",
    "#    parser.add_argument('--gender', type=int, help='% alloc to Gender Diversity', required=True)\n",
    "#    args = parser.parse_args()\n",
    "#    main(args)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 18,
   "id": "2f2ab158",
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "usage: ipykernel_launcher.py [-h] [--amount AMOUNT] --diversified DIVERSIFIED\n",
      "                             --water WATER --energy ENERGY --health HEALTH\n",
      "                             --disease DISEASE --gender GENDER\n",
      "ipykernel_launcher.py: error: the following arguments are required: --diversified, --water, --energy, --health, --disease, --gender\n"
     ]
    },
    {
     "ename": "SystemExit",
     "evalue": "2",
     "output_type": "error",
     "traceback": [
      "An exception has occurred, use %tb to see the full traceback.\n",
      "\u001b[1;31mSystemExit\u001b[0m\u001b[1;31m:\u001b[0m 2\n"
     ]
    }
   ],
   "source": [
    "import argparse\n",
    "parser = argparse.ArgumentParser()\n",
    "parser.add_argument('--amount', help='$ amount to allocate, if no value specified then uses current account equity')\n",
    "parser.add_argument('--diversified', type=int, help='% alloc to Diversified SRI(high ESG performance)', required=True)\n",
    "parser.add_argument('--water', type=int, help='% alloc to Clean Water', required=True)\n",
    "parser.add_argument('--energy', type=int, help='% alloc to Renewable Energy', required=True)\n",
    "parser.add_argument('--health', type=int, help='% alloc to Healthy Living', required=True)\n",
    "parser.add_argument('--disease', type=int, help='% alloc to Disease Eradication', required=True)\n",
    "parser.add_argument('--gender', type=int, help='% alloc to Gender Diversity', required=True)\n",
    "args = parser.parse_args()\n",
    "#args\n",
    "#main(args)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "ea81bb93",
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python [conda env:pyvizenv] *",
   "language": "python",
   "name": "conda-env-pyvizenv-py"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.7.11"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
