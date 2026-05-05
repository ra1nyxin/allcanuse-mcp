from __future__ import annotations

import ctypes
import platform
import time
from pathlib import Path
from typing import Any

HRESULT = ctypes.c_long
UINT32 = ctypes.c_uint32
UINT64 = ctypes.c_uint64
LPVOID = ctypes.c_void_p
WCHAR_PTR = ctypes.c_void_p

_WINFUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, value: str) -> GUID:
        import uuid

        parsed = uuid.UUID(value)
        data = parsed.bytes_le
        instance = cls()
        instance.Data1 = int.from_bytes(data[0:4], "little")
        instance.Data2 = int.from_bytes(data[4:6], "little")
        instance.Data3 = int.from_bytes(data[6:8], "little")
        instance.Data4[:] = data[8:16]
        return instance


def _guid(value: str) -> GUID:
    return GUID.from_string(value)


MF_VERSION = 0x00020070
COINIT_MULTITHREADED = 0x0
MFSTARTUP_FULL = 0x0

MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE = _guid("c60ac5fe-252a-478f-a0ef-bc8fa5f7cad3")
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID = _guid("8ac3587a-4ae7-42d8-99e0-0a6013eef90f")
MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME = _guid("60d0e559-52f8-4fa2-bbce-acdb34a8ec01")
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK = _guid("58f0aad8-22bf-4f8a-bb3d-d2c4978c6e2f")
MF_SOURCE_READER_ENABLE_VIDEO_PROCESSING = _guid("fb394f3d-ccf1-42ee-bbb3-f9b845d5681d")
MF_MT_MAJOR_TYPE = _guid("48eba18e-f8c9-4687-bf11-0a74c9f96a8f")
MF_MT_SUBTYPE = _guid("f7e34c9a-42e8-4714-b74b-cb29d72c35e5")
MF_MT_FRAME_SIZE = _guid("1652c33d-d6b2-4012-b834-72030849a37d")
MFMediaType_Video = _guid("73646976-0000-0010-8000-00aa00389b71")
MFVideoFormat_RGB32 = _guid("00000016-0000-0010-8000-00aa00389b71")

MF_SOURCE_READER_FIRST_VIDEO_STREAM = 0xFFFFFFFC
RPC_E_CHANGED_MODE = 0x80010106

IMFATTRIBUTES_GETUINT64 = 8
IMFATTRIBUTES_GETALLOCATEDSTRING = 13
IMFATTRIBUTES_SETUINT32 = 21
IMFATTRIBUTES_SETGUID = 24
IMFATTRIBUTES_SETSTRING = 25

IMFSOURCEREADER_GETCURRENTMEDIATYPE = 6
IMFSOURCEREADER_SETCURRENTMEDIATYPE = 7
IMFSOURCEREADER_READSAMPLE = 9

IMFMEDIASOURCE_SHUTDOWN = 12
IMFSAMPLE_CONVERTTOCONTIGUOUSBUFFER = 41
IMFMEDIABUFFER_LOCK = 3
IMFMEDIABUFFER_UNLOCK = 4


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _load_dll(name: str):
    if not _is_windows():
        return None
    try:
        return ctypes.WinDLL(name)
    except OSError:
        return None


def _load_mf():
    return _load_dll("mfplat"), _load_dll("mfreadwrite"), _load_dll("mf"), _load_dll("ole32")


def media_foundation_available() -> bool:
    mfplat, mfreadwrite, _, _ = _load_mf()
    return mfplat is not None and mfreadwrite is not None


def _hr_succeeded(hr: int) -> bool:
    return hr >= 0


def _hr_code(hr: int) -> int:
    return int(hr) & 0xFFFFFFFF


def _hr_hex(hr: int) -> str:
    return f"0x{_hr_code(hr):08X}"


def _com_invoke(ptr: ctypes.c_void_p, index: int, restype, argtypes, *args):
    address = ptr.value if isinstance(ptr, ctypes.c_void_p) else int(ptr)
    vtable = ctypes.cast(ctypes.c_void_p(address), ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn = _WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])
    return fn(ctypes.c_void_p(address), *args)


def _com_release(ptr: ctypes.c_void_p) -> None:
    if ptr and ptr.value:
        _com_invoke(ptr, 2, UINT32, [])


def _read_allocated_string(ptr: ctypes.c_void_p, guid: GUID) -> str | None:
    value_ptr = ctypes.c_void_p()
    length = UINT32()
    hr = _com_invoke(
        ptr,
        IMFATTRIBUTES_GETALLOCATEDSTRING,
        HRESULT,
        [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(UINT32)],
        ctypes.byref(guid),
        ctypes.byref(value_ptr),
        ctypes.byref(length),
    )
    if not _hr_succeeded(hr) or not value_ptr.value:
        return None
    try:
        return ctypes.wstring_at(value_ptr.value)
    finally:
        _, _, _, ole32 = _load_mf()
        if ole32 is not None:
            ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            ole32.CoTaskMemFree.restype = None
            ole32.CoTaskMemFree(value_ptr)


def _create_attributes(mfplat, initial_size: int = 1) -> ctypes.c_void_p | None:
    attrs = ctypes.c_void_p()
    mfplat.MFCreateAttributes.argtypes = [ctypes.POINTER(ctypes.c_void_p), UINT32]
    mfplat.MFCreateAttributes.restype = HRESULT
    hr = mfplat.MFCreateAttributes(ctypes.byref(attrs), initial_size)
    if not _hr_succeeded(hr):
        return None
    return attrs


def _create_media_type(mfplat) -> ctypes.c_void_p | None:
    media_type = ctypes.c_void_p()
    mfplat.MFCreateMediaType.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    mfplat.MFCreateMediaType.restype = HRESULT
    hr = mfplat.MFCreateMediaType(ctypes.byref(media_type))
    if not _hr_succeeded(hr):
        return None
    return media_type


def _set_guid(ptr: ctypes.c_void_p, index: int, guid: GUID, value: GUID) -> int:
    return _com_invoke(
        ptr,
        index,
        HRESULT,
        [ctypes.POINTER(GUID), ctypes.POINTER(GUID)],
        ctypes.byref(guid),
        ctypes.byref(value),
    )


def _set_uint32(ptr: ctypes.c_void_p, index: int, guid: GUID, value: int) -> int:
    return _com_invoke(
        ptr,
        index,
        HRESULT,
        [ctypes.POINTER(GUID), UINT32],
        ctypes.byref(guid),
        UINT32(value),
    )


def _set_string(ptr: ctypes.c_void_p, index: int, guid: GUID, value: str) -> int:
    return _com_invoke(
        ptr,
        index,
        HRESULT,
        [ctypes.POINTER(GUID), ctypes.c_wchar_p],
        ctypes.byref(guid),
        value,
    )


def _get_uint64(ptr: ctypes.c_void_p, index: int, guid: GUID) -> tuple[int, int] | None:
    value = UINT64()
    hr = _com_invoke(
        ptr,
        index,
        HRESULT,
        [ctypes.POINTER(GUID), ctypes.POINTER(UINT64)],
        ctypes.byref(guid),
        ctypes.byref(value),
    )
    if not _hr_succeeded(hr):
        return None
    width = (value.value >> 32) & 0xFFFFFFFF
    height = value.value & 0xFFFFFFFF
    return int(width), int(height)


def _release_array_and_values(items: ctypes.POINTER(ctypes.c_void_p) | None, count: int) -> None:
    if not items:
        return
    for i in range(count):
        value = items[i]
        if value:
            _com_release(ctypes.c_void_p(value))
    _, _, _, ole32 = _load_mf()
    if ole32 is not None:
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole32.CoTaskMemFree.restype = None
        ole32.CoTaskMemFree(ctypes.cast(items, ctypes.c_void_p))


def _init_media_foundation():
    mfplat, mfreadwrite, mf, ole32 = _load_mf()
    if mfplat is None or mfreadwrite is None or mf is None or ole32 is None:
        return None

    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    ole32.CoInitializeEx.restype = HRESULT
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    com_initialized = hr in (0, 1)
    if hr not in (0, 1) and _hr_code(hr) != RPC_E_CHANGED_MODE:
        return None

    mfplat.MFStartup.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    mfplat.MFStartup.restype = HRESULT
    hr = mfplat.MFStartup(MF_VERSION, MFSTARTUP_FULL)
    if not _hr_succeeded(hr):
        if com_initialized:
            ole32.CoUninitialize()
        return None

    return {
        "mfplat": mfplat,
        "mfreadwrite": mfreadwrite,
        "mf": mf,
        "ole32": ole32,
        "com_initialized": com_initialized,
    }


def _shutdown_media_foundation(state) -> None:
    mfplat = state["mfplat"]
    ole32 = state["ole32"]
    mfplat.MFShutdown.argtypes = []
    mfplat.MFShutdown.restype = HRESULT
    try:
        mfplat.MFShutdown()
    finally:
        if state.get("com_initialized"):
            ole32.CoUninitialize()


def list_video_capture_devices(*, max_devices: int = 8) -> dict[str, Any]:
    state = _init_media_foundation()
    if state is None:
        return {"ok": False, "error": "Media Foundation is not available.", "devices": []}

    mfplat = state["mfplat"]
    mf = state["mf"]
    try:
        attrs = _create_attributes(mfplat, 1)
        if attrs is None:
            return {"ok": False, "error": "Unable to create Media Foundation attributes.", "devices": []}
        if not _hr_succeeded(_set_guid(attrs, IMFATTRIBUTES_SETGUID, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID)):
            return {"ok": False, "error": "Unable to set video device source type.", "devices": []}

        mf.MFEnumDeviceSources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)), ctypes.POINTER(UINT32)]
        mf.MFEnumDeviceSources.restype = HRESULT
        activates = ctypes.POINTER(ctypes.c_void_p)()
        count = UINT32()
        hr = mf.MFEnumDeviceSources(attrs, ctypes.byref(activates), ctypes.byref(count))
        if not _hr_succeeded(hr):
            return {"ok": False, "error": f"MFEnumDeviceSources failed: {_hr_hex(hr)}", "devices": []}

        devices: list[dict[str, Any]] = []
        try:
            total = min(int(count.value), max(1, max_devices))
            for index in range(total):
                activate = ctypes.c_void_p(activates[index])
                friendly_name = _read_allocated_string(activate, MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME)
                symbolic_link = _read_allocated_string(activate, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK)
                devices.append(
                    {
                        "index": index,
                        "backend": "media-foundation",
                        "name": friendly_name,
                        "symbolic_link": symbolic_link,
                    }
                )
        finally:
            _release_array_and_values(activates, int(count.value))
        return {"ok": True, "count": len(devices), "devices": devices}
    finally:
        _com_release(attrs)
        _shutdown_media_foundation(state)


def capture_camera_photo_with_media_foundation(
    camera_index: int,
    target: Path,
    *,
    warmup_ms: int = 10_000,
) -> dict[str, Any]:
    state = _init_media_foundation()
    if state is None:
        return {"ok": False, "backend": "media-foundation", "error": "Media Foundation is not available."}

    mfplat = state["mfplat"]
    mfreadwrite = state["mfreadwrite"]
    mf = state["mf"]
    try:
        attrs = _create_attributes(mfplat, 1)
        if attrs is None:
            return {"ok": False, "backend": "media-foundation", "error": "Unable to create device enumeration attributes."}
        if not _hr_succeeded(_set_guid(attrs, IMFATTRIBUTES_SETGUID, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID)):
            return {"ok": False, "backend": "media-foundation", "error": "Unable to set video device source type."}

        mf.MFEnumDeviceSources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)), ctypes.POINTER(UINT32)]
        mf.MFEnumDeviceSources.restype = HRESULT
        activates = ctypes.POINTER(ctypes.c_void_p)()
        count = UINT32()
        hr = mf.MFEnumDeviceSources(attrs, ctypes.byref(activates), ctypes.byref(count))
        if not _hr_succeeded(hr):
            return {"ok": False, "backend": "media-foundation", "error": f"MFEnumDeviceSources failed: {_hr_hex(hr)}"}
        if camera_index >= int(count.value):
            _release_array_and_values(activates, int(count.value))
            return {"ok": False, "backend": "media-foundation", "error": f"Camera index {camera_index} was not found."}

        selected = ctypes.c_void_p(activates[camera_index])
        symbolic_link = _read_allocated_string(selected, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK)
        if not symbolic_link:
            _release_array_and_values(activates, int(count.value))
            return {"ok": False, "backend": "media-foundation", "error": "Unable to read camera symbolic link."}

        source_attrs = _create_attributes(mfplat, 2)
        if source_attrs is None:
            _release_array_and_values(activates, int(count.value))
            return {"ok": False, "backend": "media-foundation", "error": "Unable to create device source attributes."}
        if not _hr_succeeded(_set_guid(source_attrs, IMFATTRIBUTES_SETGUID, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID)):
            _release_array_and_values(activates, int(count.value))
            return {"ok": False, "backend": "media-foundation", "error": "Unable to set device source type."}
        if not _hr_succeeded(_set_string(source_attrs, IMFATTRIBUTES_SETSTRING, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK, symbolic_link)):
            _release_array_and_values(activates, int(count.value))
            return {"ok": False, "backend": "media-foundation", "error": "Unable to set camera symbolic link."}

        mf.MFCreateDeviceSource.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        mf.MFCreateDeviceSource.restype = HRESULT
        source = ctypes.c_void_p()
        hr = mf.MFCreateDeviceSource(source_attrs, ctypes.byref(source))
        _release_array_and_values(activates, int(count.value))
        _com_release(source_attrs)
        if not _hr_succeeded(hr) or not source.value:
            return {"ok": False, "backend": "media-foundation", "error": f"MFCreateDeviceSource failed: {_hr_hex(hr)}"}

        try:
            reader_attrs = _create_attributes(mfplat, 1)
            if reader_attrs is None:
                return {"ok": False, "backend": "media-foundation", "error": "Unable to create source reader attributes."}
            if not _hr_succeeded(_set_uint32(reader_attrs, IMFATTRIBUTES_SETUINT32, MF_SOURCE_READER_ENABLE_VIDEO_PROCESSING, 1)):
                return {"ok": False, "backend": "media-foundation", "error": "Unable to enable source reader video processing."}

            mfreadwrite.MFCreateSourceReaderFromMediaSource.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
            mfreadwrite.MFCreateSourceReaderFromMediaSource.restype = HRESULT
            reader = ctypes.c_void_p()
            hr = mfreadwrite.MFCreateSourceReaderFromMediaSource(source, reader_attrs, ctypes.byref(reader))
            _com_release(reader_attrs)
            if not _hr_succeeded(hr) or not reader.value:
                return {"ok": False, "backend": "media-foundation", "error": f"MFCreateSourceReaderFromMediaSource failed: {_hr_hex(hr)}"}

            try:
                media_type = _create_media_type(mfplat)
                if media_type is None:
                    return {"ok": False, "backend": "media-foundation", "error": "Unable to create media type."}
                if not _hr_succeeded(_set_guid(media_type, IMFATTRIBUTES_SETGUID, MF_MT_MAJOR_TYPE, MFMediaType_Video)):
                    return {"ok": False, "backend": "media-foundation", "error": "Unable to set media major type."}
                if not _hr_succeeded(_set_guid(media_type, IMFATTRIBUTES_SETGUID, MF_MT_SUBTYPE, MFVideoFormat_RGB32)):
                    return {"ok": False, "backend": "media-foundation", "error": "Unable to set RGB32 media subtype."}

                hr = _com_invoke(
                    reader,
                    IMFSOURCEREADER_SETCURRENTMEDIATYPE,
                    HRESULT,
                    [UINT32, ctypes.c_void_p, ctypes.c_void_p],
                    UINT32(MF_SOURCE_READER_FIRST_VIDEO_STREAM),
                    None,
                    media_type,
                )
                if not _hr_succeeded(hr):
                    hr = _com_invoke(
                        reader,
                        IMFSOURCEREADER_SETCURRENTMEDIATYPE,
                        HRESULT,
                        [UINT32, ctypes.c_void_p, ctypes.c_void_p],
                        UINT32(0),
                        None,
                        media_type,
                    )
                if not _hr_succeeded(hr):
                    return {"ok": False, "backend": "media-foundation", "error": f"SetCurrentMediaType failed: {_hr_hex(hr)}"}

                current_type = ctypes.c_void_p()
                hr = _com_invoke(
                    reader,
                    IMFSOURCEREADER_GETCURRENTMEDIATYPE,
                    HRESULT,
                    [UINT32, ctypes.POINTER(ctypes.c_void_p)],
                    UINT32(MF_SOURCE_READER_FIRST_VIDEO_STREAM),
                    ctypes.byref(current_type),
                )
                if not _hr_succeeded(hr) or not current_type.value:
                    hr = _com_invoke(
                        reader,
                        IMFSOURCEREADER_GETCURRENTMEDIATYPE,
                        HRESULT,
                        [UINT32, ctypes.POINTER(ctypes.c_void_p)],
                        UINT32(0),
                        ctypes.byref(current_type),
                    )
                if not _hr_succeeded(hr) or not current_type.value:
                    return {"ok": False, "backend": "media-foundation", "error": f"GetCurrentMediaType failed: {_hr_hex(hr)}"}

                try:
                    size = _get_uint64(current_type, IMFATTRIBUTES_GETUINT64, MF_MT_FRAME_SIZE)
                    if not size:
                        return {"ok": False, "backend": "media-foundation", "error": "Unable to determine frame size."}
                    width, height = size

                    warmup_ms = max(0, min(int(warmup_ms), 10_000))
                    warmup_frames_discarded = 0
                    deadline = time.monotonic() + warmup_ms / 1000 if warmup_ms > 0 else None
                    while deadline is not None and time.monotonic() < deadline:
                        sample = _read_sample(reader, MF_SOURCE_READER_FIRST_VIDEO_STREAM)
                        if sample is None:
                            sample = _read_sample(reader, 0)
                        if sample is None:
                            time.sleep(0.05)
                            continue
                        warmup_frames_discarded += 1
                        _com_release(sample)

                    sample = _read_sample(reader, MF_SOURCE_READER_FIRST_VIDEO_STREAM)
                    if sample is None:
                        sample = _read_sample(reader, 0)
                    if sample is None:
                        return {"ok": False, "backend": "media-foundation", "error": "No frame was produced by the source reader."}

                    try:
                        buffer = ctypes.c_void_p()
                        hr = _com_invoke(sample, IMFSAMPLE_CONVERTTOCONTIGUOUSBUFFER, HRESULT, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(buffer))
                        if not _hr_succeeded(hr) or not buffer.value:
                            return {"ok": False, "backend": "media-foundation", "error": f"ConvertToContiguousBuffer failed: {_hr_hex(hr)}"}

                        try:
                            return _buffer_to_png_result(
                                buffer,
                                target,
                                width=width,
                                height=height,
                                warmup_ms=warmup_ms,
                                warmup_frames_discarded=warmup_frames_discarded,
                                camera_index=camera_index,
                            )
                        finally:
                            _com_release(buffer)
                    finally:
                        _com_release(sample)
                finally:
                    _com_release(current_type)
            finally:
                _com_release(reader)
        finally:
            _com_invoke(source, IMFMEDIASOURCE_SHUTDOWN, HRESULT, [])
            _com_release(source)
    finally:
        _com_release(attrs)
        _shutdown_media_foundation(state)


def _read_sample(reader: ctypes.c_void_p, stream_index: int) -> ctypes.c_void_p | None:
    stream = UINT32()
    flags = UINT32()
    timestamp = ctypes.c_longlong()
    sample = ctypes.c_void_p()
    hr = _com_invoke(
        reader,
        IMFSOURCEREADER_READSAMPLE,
        HRESULT,
        [UINT32, UINT32, ctypes.POINTER(UINT32), ctypes.POINTER(UINT32), ctypes.POINTER(ctypes.c_longlong), ctypes.POINTER(ctypes.c_void_p)],
        UINT32(stream_index),
        UINT32(0),
        ctypes.byref(stream),
        ctypes.byref(flags),
        ctypes.byref(timestamp),
        ctypes.byref(sample),
    )
    if not _hr_succeeded(hr) or not sample.value:
        return None
    return sample


def _buffer_to_png_result(
    buffer: ctypes.c_void_p,
    target: Path,
    *,
    width: int,
    height: int,
    warmup_ms: int,
    warmup_frames_discarded: int,
    camera_index: int,
) -> dict[str, Any]:
    try:
        from PIL import Image

        data_ptr = ctypes.c_void_p()
        max_len = UINT32()
        cur_len = UINT32()
        hr = _com_invoke(
            buffer,
            IMFMEDIABUFFER_LOCK,
            HRESULT,
            [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(UINT32), ctypes.POINTER(UINT32)],
            ctypes.byref(data_ptr),
            ctypes.byref(max_len),
            ctypes.byref(cur_len),
        )
        if not _hr_succeeded(hr) or not data_ptr.value:
            return {"ok": False, "backend": "media-foundation", "error": f"IMFMediaBuffer::Lock failed: {_hr_hex(hr)}"}

        try:
            raw = ctypes.string_at(data_ptr.value, int(cur_len.value))
        finally:
            _com_invoke(buffer, IMFMEDIABUFFER_UNLOCK, HRESULT, [])

        if not raw:
            return {"ok": False, "backend": "media-foundation", "error": "Captured buffer was empty."}

        stride = int(len(raw) // max(1, height))
        if stride <= 0:
            stride = width * 4

        image = Image.frombytes("RGB", (width, height), raw, "raw", "BGRX", stride, 1)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)

        result = {
            "ok": True,
            "platform": "Windows",
            "backend": "media-foundation",
            "path": str(target),
            "camera_index": camera_index,
            "width": width,
            "height": height,
            "file_size": target.stat().st_size,
            "warmup_ms": warmup_ms,
            "warmup_frames_discarded": warmup_frames_discarded,
        }
        return result
    except Exception as exc:
        return {"ok": False, "backend": "media-foundation", "error": str(exc)}
