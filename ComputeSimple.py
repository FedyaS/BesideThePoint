from BesideThePoint import trial

def runTrials(n):
    solutions = 0
    for _ in range(n):
        res = trial()
        if res['solution'] == 'Solution':
            solutions += 1
    return solutions / n

print(runTrials(15000000))