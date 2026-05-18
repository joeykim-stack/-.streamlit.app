import os

file_name = "Jan.csv"

print(f"🕵️‍♂️ === [{file_name}] 파일 내부 X레이 진단 === 🕵️‍♂️\n")

if not os.path.exists(file_name):
    print(f"🚨 앗! 폴더 안에 '{file_name}' 파일이 아예 없습니다. 위치나 이름을 다시 확인해주세요.")
else:
    success = False
    for enc in ['cp949', 'utf-8-sig', 'euc-kr']:
        try:
            with open(file_name, 'r', encoding=enc) as f:
                print(f"🟢 [{enc}] 인코딩으로 열기 성공! 내부 데이터 1~5번 줄을 보여줍니다:\n")
                for i in range(5):
                    line = f.readline().strip()
                    print(f"[{i+1}번줄] {line}")
                success = True
                break
        except UnicodeDecodeError:
            continue # 인코딩이 안 맞으면 다음 녀석으로 시도
        except Exception as e:
            print(f"🚨 [에러 발생] 파일을 텍스트로 읽을 수 없습니다. (이름만 바꾼 엑셀 파일일 확률 99%): {e}")
            break

    if not success:
        print("\n🚨 결론: 이 파일은 정상적인 CSV 텍스트 파일이 아닙니다!")