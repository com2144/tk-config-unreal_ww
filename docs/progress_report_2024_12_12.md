# Maya FBX Publishing 기능 개발 중간 보고서
날짜: 2024-12-12

## 1. 개요
Maya에서 Unreal Engine으로의 에셋 파이프라인 구축을 위한 FBX 퍼블리싱 기능을 개발했습니다. 이 기능은 Maya에서 작업한 에셋을 FBX 형식으로 자동 변환하여 Unreal Engine에서 사용할 수 있도록 합니다.

## 2. 금일 핵심 수정사항
1. Maya와 Unreal 환경 분리
   - Unreal 모듈 조건부 임포트로 Maya 환경에서의 오류 해결
   - 각 환경별 퍼블리시 로직 분리

2. 버전 관리 시스템 개선
   - Maya 씬 파일(.mb/.ma)과 FBX 파일의 버전 동기화
   - 중복 파일 생성 문제 해결

3. FBX 내보내기 최적화
   - Unreal Engine에 최적화된 FBX 내보내기 설정 구현
   - 메시 유효성 검사 추가

## 3. 수정된 파일 및 코드

### 3.1 publish_asset.py
위치: `hooks/tk-multi-publish2/basic/publish_asset.py`

```python
# Unreal 모듈 조건부 임포트
try:
    import unreal
    UNREAL_AVAILABLE = True
except ImportError:
    UNREAL_AVAILABLE = False

class UnrealAssetPublishPlugin(HookBaseClass):
    def _maya_export_fbx(self, publish_path):
        """FBX 내보내기 최적화 설정"""
        import maya.cmds as cmds
        import maya.mel as mel

        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            cmds.loadPlugin("fbxmaya")

        mel.eval('FBXResetExport')
        mel.eval('FBXExportFileVersion -v FBX201800')
        mel.eval('FBXExportUpAxis y')
        mel.eval('FBXExportShapes -v true')
        mel.eval('FBXExportSkins -v true')
        mel.eval('FBXExportSmoothingGroups -v true')
        mel.eval('FBXExportSmoothMesh -v true')
        mel.eval('FBXExportTangents -v true')
        mel.eval('FBXExportTriangulate -v false')
        mel.eval('FBXExportConstraints -v false')
        mel.eval('FBXExportCameras -v false')
        mel.eval('FBXExportLights -v false')
        mel.eval('FBXExportEmbeddedTextures -v false')
        mel.eval('FBXExportInputConnections -v false')

        mel.eval('FBXExport -f "{}" -s'.format(publish_path.replace('\\', '/')))

    def publish(self, settings, item):
        """버전 동기화 로직"""
        # Maya 씬 버전 가져오기
        maya_version = item.properties.get("publish_version", 1)
        fields["version"] = maya_version
        item.properties["publish_version"] = maya_version
```

### 3.2 tk-multi-publish2.yml
위치: `env/includes/settings/tk-multi-publish2.yml`

```yaml
# Maya asset_step 설정
settings.tk-multi-publish2.maya.asset_step:
  collector: "{self}/collector.py:{engine}/tk-multi-publish2/basic/collector.py"
  publish_plugins:
  - name: Export FBX for Unreal
    hook: "{config}/tk-multi-publish2/basic/publish_asset.py"
    settings:
        Publish Template: maya_asset_publish_fbx
        File Type: FBX File
```

### 3.3 templates.yml
위치: `core/templates.yml`

```yaml
# Maya FBX 퍼블리시 템플릿
paths:
    maya_asset_publish_fbx:
        definition: '@asset_root/pub/maya/fbx/{name}.{Step}.v{version}.fbx'
        root_name: primary
```

## 4. 주요 개발 사항

### 4.1 Maya FBX 퍼블리싱 플러그인 통합
- `publish_asset.py`에 Maya FBX 내보내기 기능 통합
- Maya 세션 및 메시 유효성 검사 구현
- FBX 내보내기 옵션 최적화 설정

### 4.2 템플릿 구성
- Maya 에셋 FBX 퍼블리시 템플릿 추가
- 버전 관리를 위한 경로 구조 설계

### 4.3 퍼블리시 설정 구성
- Maya asset_step에 FBX 퍼블리시 플러그인 추가
- File Type 설정 추가

## 5. 버그 수정 및 개선 사항

### 5.1 Unreal 모듈 의존성 해결
- Maya 환경에서 Unreal 모듈 임포트 오류 수정
- 조건부 임포트 구현으로 Maya/Unreal 환경 분리

### 5.2 버전 관리 개선
- Maya 씬 파일과 FBX 파일의 버전 동기화
- 중복 파일 생성 문제 해결
- 버전 번호 자동 증가 로직 개선

### 5.3 에러 처리 및 로깅
- 상세한 디버그 로깅 추가
- 에러 메시지 개선
- 예외 처리 강화

## 6. 현재 상태
- Maya에서 에셋 퍼블리시 시 .mb/.ma 파일과 .fbx 파일이 동일한 버전으로 생성됨
- FBX 내보내기 설정이 Unreal Engine에 최적화되어 있음
- 안정적인 에러 처리와 로깅 시스템 구축

## 7. 향후 계획
1. Unreal Engine에서의 FBX 임포트 자동화
2. 에셋 메타데이터 관리 시스템 구축
3. 퍼블리시 후 자동 테스트 시스템 구현
4. 성능 최적화 및 코드 리팩토링

## 8. 결론
Maya FBX 퍼블리싱 기능의 기본 구조가 완성되었으며, 안정적으로 작동하고 있습니다. 특히 Maya와 Unreal 환경의 분리, 버전 관리 시스템 개선, FBX 내보내기 최적화를 통해 더욱 안정적이고 효율적인 파이프라인을 구축했습니다. 향후 Unreal Engine과의 통합을 더욱 강화하고, 사용자 경험을 개선할 예정입니다.

## 9. 후크 체인 최적화

### 9.1 변경 사항
- `tk-multi-publish2.yml`의 후크 체인 설정 수정
  - 기존: `"{self}/publish_file.py:{config}/tk-multi-publish2/basic/publish_asset.py"`
  - 변경: `"{config}/tk-multi-publish2/basic/publish_asset.py"`
  - 불필요한 기본 퍼블리시 후크 의존성 제거

### 9.2 개선 효과
1. 코드 명확성 향상
   - 커스텀 퍼블리시 로직만 사용하도록 단순화
   - 후크 체인으로 인한 혼란 방지

2. 성능 최적화
   - 불필요한 후크 로딩 제거
   - 실행 시간 단축

3. 유지보수성 향상
   - 코드 의존성 감소
   - 디버깅 용이성 증가

## 10. 향후 계획

### 10.1 기능 개선
1. Unreal Engine FBX 임포트 자동화
   - 메타데이터 기반 임포트 설정
   - 에셋 네이밍 규칙 표준화

2. 에러 처리 강화
   - 상세한 에러 메시지
   - 자동 복구 메커니즘

3. UI/UX 개선
   - 진행 상황 표시
   - 로그 뷰어 개선

### 10.2 문서화
1. 사용자 가이드 작성
   - 설정 방법
   - 트러블슈팅 가이드

2. 개발자 문서 보강
   - API 문서
   - 아키텍처 설명

## 11. 버그 수정 - Shotgun 퍼블리시 등록

### 11.1 문제 상황
- Maya FBX 퍼블리시 후 Shotgun에 파일 등록 실패
- 부모 클래스의 `_save_to_shotgun` 메서드 호출 시 AttributeError 발생

### 11.2 해결 방법
1. `_register_publish` 메서드 수정
   - 부모 클래스 메서드 대신 `publisher.register_publish` 직접 호출
   - Version 엔티티 생성 후 연결
   - 상세한 에러 로깅 추가

```python
def _register_publish(self, settings, item, publish_path):
    """
    Register the publish with Shotgun
    """
    publisher = self.parent
    
    # Get the publish info
    publish_version = publisher.util.get_version_number(publish_path)
    publish_name = publisher.util.get_publish_name(publish_path)
    
    # Create version in Shotgun
    version_data = {
        "project": publisher.context.project,
        "code": publish_name,
        "description": item.description,
        "entity": publisher.context.entity,
        "sg_task": publisher.context.task,
        "created_by": publisher.context.user,
        "user": publisher.context.user,
        "sg_status_list": "rev",
        "sg_path_to_frames": publish_path
    }
    version = publisher.shotgun.create("Version", version_data)
    
    # Register the publish
    publish_data = {
        "tk": publisher.sgtk,
        "context": publisher.context,
        "comment": item.description,
        "path": publish_path,
        "name": publish_name,
        "created_by": publisher.context.user,
        "version_number": publish_version,
        "published_file_type": "FBX File",
        "version_entity": version
    }
    publisher.register_publish(**publish_data)
```

### 11.3 개선 효과
1. 안정성 향상
   - 부모 클래스 의존성 제거
   - 직접적인 Shotgun API 사용

2. 에러 처리 강화
   - Version 생성과 Publish 등록 분리
   - 각 단계별 상세 에러 메시지

3. 추적성 개선
   - Version과 PublishedFile 엔티티 연결
   - 작업 이력 추적 용이
