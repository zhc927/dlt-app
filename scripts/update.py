#!/usr/bin/env python3
"""Fetch published DLT results. Refuse invalid or conflicting draws."""
import datetime as dt,json,pathlib,re,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data/history.json"
BASE="https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
def fetch(page):
    q=urllib.parse.urlencode(dict(gameNo=85,provinceId=0,pageSize=100,pageNo=page,isVerify=1,termLimits=0))
    req=urllib.request.Request(BASE+"?"+q,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def parse(d):
    issue=str(d.get("lotteryDrawNum") or d.get("drawNum") or "")
    raw=str(d.get("lotteryDrawResult") or d.get("drawResult") or "")
    nums=[int(x) for x in re.findall(r"\d+",raw)]
    date=str(d.get("lotteryDrawTime") or d.get("drawTime") or "")[:10]
    if not re.fullmatch(r"\d{5,8}",issue) or len(nums)!=7 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date):raise ValueError("Invalid draw format "+issue)
    f,b=sorted(nums[:5]),sorted(nums[5:])
    if len(set(f))!=5 or len(set(b))!=2 or any(x<1 or x>35 for x in f) or any(x<1 or x>12 for x in b):raise ValueError("Invalid balls "+issue)
    return dict(issue=issue,date=date,f=f,b=b)
def main():
    old=json.loads(OUT.read_text()) if OUT.exists() else {"draws":[]}
    records={d["issue"]:d for d in old["draws"]}
    got=0
    for p in range(1,31):
        payload=fetch(p)
        value=payload.get("value") or {}
        items=value.get("list") if isinstance(value,dict) else None
        if not isinstance(items,list):raise RuntimeError("Unexpected source schema")
        for item in items:
            d=parse(item)
            if d["issue"] in records and records[d["issue"]]!=d:raise RuntimeError("Conflicting issue "+d["issue"])
            records[d["issue"]]=d;got+=1
        if len(items)<100:break
    if not got:raise RuntimeError("Source returned zero draws")
    ordered=sorted(records.values(),key=lambda d:(d["date"],int(d["issue"])))
    if ordered==old.get("draws"):print("No change");return
    OUT.write_text(json.dumps({"source":BASE,"updated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"draws":ordered},ensure_ascii=False,separators=(",",":"))+"\n")
    print("Saved",len(ordered),"draws")
if __name__=="__main__":main()
