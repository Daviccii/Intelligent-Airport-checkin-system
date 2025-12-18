import re
p='c:/Users/Administrator/Downloads/Intelligent-Airport-checkin-system/frontend/availability.html'
s=open(p,'r',encoding='utf-8').read()
m=re.search(r'<script[^>]*>(.*)</script>', s, flags=re.S)
if not m:
    print('No <script> block found')
    raise SystemExit(1)
code=m.group(1)
# remove comments
code_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', code, flags=re.S | re.M)
stack=[]
line_no=1
in_single=False
in_double=False
in_back=False
escaped=False
for ch in code_no_comments:
    if ch=='\n':
        line_no+=1
        continue
    if escaped:
        escaped=False
        continue
    if ch=='\\':
        escaped=True
        continue
    if in_single:
        if ch=="'": in_single=False
        continue
    if in_double:
        if ch=='"': in_double=False
        continue
    if in_back:
        if ch=='`': in_back=False
        continue
    if ch=="'": in_single=True; continue
    if ch=='"': in_double=True; continue
    if ch=='`': in_back=True; continue
    if ch=='{': stack.append(line_no)
    if ch=='}':
        if stack:
            stack.pop()
        else:
            print('Extra closing brace at line', line_no)
print('Unmatched openings (lines):', stack)
if stack:
    # print nearby code
    for l in stack:
        start=max(1,l-3)
        print('\nContext for opening at line',l)
        for i,line in enumerate(code.splitlines(),1):
            if start<=i<=l+3:
                print(f"{i:04d}: {line}")
