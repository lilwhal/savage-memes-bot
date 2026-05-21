else:
    image_url = upload_to_imgbb(file_path)
    if not image_url:
        return False
    resp = requests.post(
        f"{GRAPH_URL}/{page_id}/photos",
        data={"caption": caption, "url": image_url, "access_token": page_token},
    )
