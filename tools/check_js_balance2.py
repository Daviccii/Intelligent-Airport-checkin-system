import re
p='c:/Users/Administrator/Downloads/Intelligent-Airport-checkin-system/frontend/availability.html'
s=open(p,'r',encoding='utf-8').read()
m=re.search(r'<script[^>]*>(.*)</script>', s, flags=re.S)
if not m:
    print('No <script> block found')
    raise SystemExit(1)
code=m.group(1)
# Remove JS comments
code_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', code, flags=re.S | re.M)
# Now iterate and ignore braces inside single, double, or backtick strings
bal=0
in_single=False
in_double=False
in_back=False
escaped=False
lines=code_no_comments.splitlines()
for i,line in enumerate(lines,1):
    j=0
    while j < len(line):
        ch=line[j]
        if escaped:
            escaped=False
            j+=1
            continue
        if ch=='\\':
            escaped=True
            j+=1
            continue
        if in_single:
            if ch=="'": in_single=False
            j+=1
            continue
        if in_double:
            if ch=='"': in_double=False
            j+=1
            continue
        if in_back:
            if ch=='`': in_back=False
            j+=1
            continue
        if ch=="'": in_single=True
        elif ch=='"': in_double=True
        elif ch=='`': in_back=True
        elif ch=='{': bal+=1
        elif ch=='}': bal-=1
        j+=1
    # print intermediate balance occasionally
    if i%50==0:
        print('line',i,'balance',bal)
print('final balance (ignoring comments/strings):',bal)
# If imbalance, show nearby lines where braces occur
if bal!=0:
    print('\nNearby brace occurrences:')
    for i,line in enumerate(lines,1):
        if '{' in line or '}' in line:
            print(f"{i:04d}: {line.strip()[:200]}")
