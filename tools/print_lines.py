p='c:/Users/Administrator/Downloads/Intelligent-Airport-checkin-system/frontend/availability.html'
with open(p,'r',encoding='utf-8') as f:
    lines=f.readlines()
for i,l in enumerate(lines,1):
    if 70<=i<=110:
        print(f"{i:04d}: {l.rstrip()}")
    if i>110: break
