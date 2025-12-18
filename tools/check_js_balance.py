import re
p='c:/Users/Administrator/Downloads/Intelligent-Airport-checkin-system/frontend/availability.html'
s=open(p,'r',encoding='utf-8').read()
m=re.search(r'<script[^>]*>(.*)</script>', s, flags=re.S)
if not m:
    print('No <script> block found')
    raise SystemExit(1)
code=m.group(1)
opens=code.count('{')
closes=code.count('}')
print('total { =',opens,'} =',closes)
# show lines where balance goes negative and final balance
balance=0
firstneg=None
for i,line in enumerate(code.splitlines(),1):
    for ch in line:
        if ch=='{': balance+=1
        elif ch=='}': balance-=1
    if firstneg is None and balance<0:
        firstneg=i
print('first negative at line:', firstneg)
print('final balance:', balance)
# Output nearby lines around where balance diverges from start
bal=0
for i,line in enumerate(code.splitlines(),1):
    prev=bal
    for ch in line:
        if ch=='{': bal+=1
        elif ch=='}': bal-=1
    if bal!=prev:
        print(f"{i:04d}: bal {prev}->{bal} | {line[:200]}")
