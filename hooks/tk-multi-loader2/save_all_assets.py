import unreal

def save_all_unsaved_assets():
    """
    콘텐츠 브라우저에서 저장되지 않은 모든 애셋을 찾아 저장합니다.
    """
    # 에디터 애셋 라이브러리 접근
    editor_lib = unreal.EditorAssetLibrary()
    
    # 모든 애셋 경로 가져오기
    all_assets = editor_lib.list_assets("/Game/", recursive=True, include_folder=False)
    
    # 저장되지 않은 애셋 카운트
    unsaved_count = 0
    
    print("저장되지 않은 애셋 검색 중...")
    
    # 각 애셋 확인 및 저장
    for asset_path in all_assets:
        # 애셋이 수정되었는지 확인
        if editor_lib.does_asset_exist(asset_path):
            try:
                # 수정된(dirty) 애셋만 저장
                if editor_lib.save_asset(asset_path, only_if_is_dirty=True):
                    print(f"저장됨: {asset_path}")
                    unsaved_count += 1
            except Exception as e:
                print(f"에러: {asset_path} 저장 실패 - {str(e)}")
    
    print(f"\n작업 완료: {unsaved_count}개의 애셋이 저장되었습니다.")

# 스크립트 실행
if __name__ == "__main__":
    with unreal.ScopedEditorTransaction("Save All Unsaved Assets") as transaction:
        save_all_unsaved_assets()