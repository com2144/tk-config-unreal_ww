# 문제 해결 가이드

## 일반적인 설정 방법

1. 가상 환경 설정
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

2. 의존성 설치
```bash
pip install -r requirements.txt
```

## 자주 발생하는 문제들

### 1. ModuleNotFoundError: No module named 'shotgun_api3'

#### 문제 원인
- 가상 환경이 활성화되지 않음
- shotgun_api3 모듈이 설치되지 않음
- 잘못된 Python 인터프리터 선택

#### 해결 방법
1. 가상 환경 활성화 확인
```bash
.venv\Scripts\activate  # Windows
```

2. 모듈 설치
```bash
python -m pip install shotgun_api3
```

3. VSCode 설정
- `Ctrl+Shift+P` → "Python: Select Interpreter" → `.venv` 환경 선택

### 2. ShotGrid API 연결 오류

#### 문제 원인
- 잘못된 API 키 또는 스크립트 이름
- 네트워크 연결 문제
- 환경 변수 미설정

#### 해결 방법
1. config.ini 파일에서 설정 확인
```ini
[shotgun]
host=https://your-site.shotgrid.autodesk.com
api_script=your_script_name
api_key=your_api_key
```

2. 네트워크 연결 테스트
```python
import shotgun_api3
sg = shotgun_api3.Shotgun("https://your-site.shotgrid.autodesk.com",
                         script_name="your_script_name",
                         api_key="your_api_key")
# 테스트 쿼리
sg.find_one("Project", [])
```

## 팁과 모범 사례

1. **의존성 관리**
   - 새로운 패키지 설치 시 requirements.txt 업데이트
   ```bash
   pip freeze > requirements.txt
   ```

2. **가상 환경 사용**
   - 프로젝트마다 별도의 가상 환경 사용
   - 전역 Python 환경 오염 방지

3. **버전 관리**
   - requirements.txt를 git에 포함
   - 환경 설정 파일은 .gitignore에 추가

4. **디버깅**
   - 로그 레벨 설정으로 자세한 오류 확인
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

## 추가 리소스
- [ShotGrid API 문서](https://developers.shotgridsoftware.com/python-api/)
- [Toolkit 개발자 문서](https://developer.shotgridsoftware.com/tk-core/)
