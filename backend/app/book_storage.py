import base64
import hashlib
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

PDF_PART_SIZE = int(os.getenv("MULTIPART_CHUNK_SIZE_BYTES", str(8 * 1024 * 1024)))
MAX_PARTS = 10_000
STREAM_BUFFER_SIZE = 1024 * 1024
MIN_S3_PART_SIZE = 5 * 1024 * 1024
MAX_S3_PART_SIZE = 5 * 1024 * 1024 * 1024
PartManifest = dict[str, dict[str, int | str]]


class BookStorage:
    provider: str

    def begin(self, key: str) -> str | None:
        raise NotImplementedError

    def authorize_part(
        self,
        key: str,
        upload_id: str | None,
        number: int,
        expected_size: int,
        expected_sha256: str,
    ) -> str | None:
        raise NotImplementedError

    async def store_local_part(
        self,
        key: str,
        number: int,
        expected_size: int,
        expected_sha256: str,
        chunks: AsyncIterator[bytes],
    ) -> str:
        raise NotImplementedError

    def complete(
        self,
        key: str,
        upload_id: str | None,
        parts: PartManifest,
        expected_size: int,
    ) -> tuple[int, str]:
        raise NotImplementedError

    def open(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def local_processing_path(self, key: str) -> tuple[Path, bool]:
        raise NotImplementedError

    def uploaded_part_sizes(self, key: str, upload_id: str | None, count: int) -> dict[str, int]:
        raise NotImplementedError

    def delete(self, key: str, upload_id: str | None = None) -> None:
        raise NotImplementedError


class LocalBookStorage(BookStorage):
    provider = "local"

    def __init__(self) -> None:
        self.root = Path(os.getenv("TEMPORARY_UPLOAD_DIRECTORY", "./private-books")).resolve()
        if os.getenv("APP_ENV", "").lower() == "production" and os.getenv(
            "LOCAL_BOOK_STORAGE_PERSISTENT", ""
        ).lower() not in ("1", "true", "yes"):
            raise RuntimeError(
                "Local book storage is disabled in production unless its volume "
                "is explicitly persistent."
            )
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.parts_root = self.root / ".parts"
        self.parts_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or key.startswith(".parts/"):
            raise ValueError("Invalid internal storage key.")
        return path

    def begin(self, key: str) -> str | None:
        self._path(key)
        return None

    def _part_dir(self, key: str) -> Path:
        directory = (self.parts_root / Path(key).stem).resolve()
        if not directory.is_relative_to(self.parts_root):
            raise ValueError("Invalid internal upload key.")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return directory

    def authorize_part(
        self,
        key: str,
        upload_id: str | None,
        number: int,
        expected_size: int,
        expected_sha256: str,
    ) -> str | None:
        return None

    async def store_local_part(
        self,
        key: str,
        number: int,
        expected_size: int,
        expected_sha256: str,
        chunks: AsyncIterator[bytes],
    ) -> str:
        part_dir = self._part_dir(key)
        destination = part_dir / f"{number:05d}.part"
        temporary = part_dir / f".{number:05d}.tmp"
        digest = hashlib.sha256()
        written = 0
        try:
            with temporary.open("wb") as output:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > expected_size:
                        raise ValueError("Upload part exceeds its expected size.")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if written != expected_size:
                raise ValueError("Upload part size does not match the expected size.")
            if digest.hexdigest() != expected_sha256:
                raise ValueError("Upload part checksum did not match.")
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return digest.hexdigest()

    def complete(
        self,
        key: str,
        upload_id: str | None,
        parts: PartManifest,
        expected_size: int,
    ) -> tuple[int, str]:
        part_dir = self._part_dir(key)
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = destination.with_suffix(".assembling")
        digest = hashlib.sha256()
        written = 0
        try:
            with temporary.open("wb") as output:
                for number in range(1, len(parts) + 1):
                    part = part_dir / f"{number:05d}.part"
                    if not part.is_file():
                        raise ValueError("An upload part is missing.")
                    part_digest = hashlib.sha256()
                    part_written = 0
                    with part.open("rb") as source:
                        while chunk := source.read(STREAM_BUFFER_SIZE):
                            written += len(chunk)
                            part_written += len(chunk)
                            digest.update(chunk)
                            part_digest.update(chunk)
                            output.write(chunk)
                    expected = parts[str(number)]
                    expected_part_size = int(expected["size"])
                    if part_written != expected_part_size:
                        raise ValueError("A stored part size does not match the upload session.")
                    if part_digest.hexdigest() != expected["sha256"]:
                        raise ValueError(
                            "A stored part checksum does not match the upload session."
                        )
                output.flush()
                os.fsync(output.fileno())
            if written != expected_size:
                raise ValueError("Completed file size does not match the upload session.")
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        shutil.rmtree(part_dir, ignore_errors=True)
        return written, digest.hexdigest()

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def local_processing_path(self, key: str) -> tuple[Path, bool]:
        return self._path(key), False

    def uploaded_part_sizes(self, key: str, upload_id: str | None, count: int) -> dict[str, int]:
        part_dir = self._part_dir(key)
        return {
            str(number): (part_dir / f"{number:05d}.part").stat().st_size
            for number in range(1, count + 1)
            if (part_dir / f"{number:05d}.part").is_file()
        }

    def delete(self, key: str, upload_id: str | None = None) -> None:
        self._path(key).unlink(missing_ok=True)
        shutil.rmtree(self._part_dir(key), ignore_errors=True)


class S3BookStorage(BookStorage):
    provider = "s3"

    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as error:
            raise RuntimeError("Install boto3 to use S3 book storage.") from error
        bucket = os.getenv("S3_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3.")
        if not MIN_S3_PART_SIZE <= PDF_PART_SIZE <= MAX_S3_PART_SIZE:
            raise RuntimeError("S3 multipart chunks must be between 5 MiB and 5 GiB.")
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=os.getenv("S3_REGION") or None,
            endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY") or None,
        )

    def begin(self, key: str) -> str:
        response = self.client.create_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            ContentType="application/pdf",
            Metadata={"private-book": "true"},
            ChecksumAlgorithm="SHA256",
        )
        return str(response["UploadId"])

    def authorize_part(
        self,
        key: str,
        upload_id: str | None,
        number: int,
        expected_size: int,
        expected_sha256: str,
    ) -> str:
        if upload_id is None:
            raise ValueError("The multipart upload session is invalid.")
        checksum = base64.b64encode(bytes.fromhex(expected_sha256)).decode("ascii")
        return str(
            self.client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": number,
                    "ChecksumSHA256": checksum,
                    "ContentLength": expected_size,
                },
                ExpiresIn=900,
            )
        )

    async def store_local_part(
        self,
        key: str,
        number: int,
        expected_size: int,
        expected_sha256: str,
        chunks: AsyncIterator[bytes],
    ) -> str:
        raise ValueError("S3 parts must be sent directly to their authorized URL.")

    def complete(
        self,
        key: str,
        upload_id: str | None,
        parts: PartManifest,
        expected_size: int,
    ) -> tuple[int, str]:
        if upload_id is None:
            raise ValueError("The multipart upload session is invalid.")
        uploaded: list[dict[str, object]] = []
        marker = 0
        while True:
            response = self.client.list_parts(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                PartNumberMarker=marker,
            )
            uploaded.extend(response.get("Parts", []))
            if not response.get("IsTruncated"):
                break
            marker = int(response["NextPartNumberMarker"])
        uploaded.sort(key=lambda part: int(part["PartNumber"]))
        if len(uploaded) != len(parts) or [int(part["PartNumber"]) for part in uploaded] != list(
            range(1, len(uploaded) + 1)
        ):
            raise ValueError("The multipart upload has missing or unexpected parts.")
        if any(
            int(part.get("Size", 0)) != int(parts[str(part["PartNumber"])]["size"])
            for part in uploaded
        ):
            raise ValueError("A stored part size does not match the upload session.")
        if any(
            part.get("ChecksumSHA256")
            != base64.b64encode(
                bytes.fromhex(str(parts[str(part["PartNumber"])]["sha256"]))
            ).decode("ascii")
            for part in uploaded
        ):
            raise ValueError("A stored part checksum does not match the upload session.")
        self.client.complete_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={
                "Parts": [
                    {
                        "PartNumber": int(part["PartNumber"]),
                        "ETag": part["ETag"],
                        "ChecksumSHA256": part["ChecksumSHA256"],
                    }
                    for part in uploaded
                ]
            },
        )
        digest = hashlib.sha256()
        actual_size = 0
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            body = response["Body"]
            while chunk := body.read(STREAM_BUFFER_SIZE):
                actual_size += len(chunk)
                digest.update(chunk)
        finally:
            response["Body"].close()
        if actual_size != expected_size:
            self.delete(key)
            raise ValueError("Completed file size does not match the upload session.")
        return actual_size, digest.hexdigest()

    def open(self, key: str) -> BinaryIO:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"]

    def local_processing_path(self, key: str) -> tuple[Path, bool]:
        fd, filename = tempfile.mkstemp(prefix="book-processing-", suffix=".pdf")
        os.close(fd)
        path = Path(filename)
        self.client.download_file(self.bucket, key, str(path))
        return path, True

    def uploaded_part_sizes(self, key: str, upload_id: str | None, count: int) -> dict[str, int]:
        if upload_id is None:
            return {}
        parts: dict[str, int] = {}
        marker = 0
        while True:
            response = self.client.list_parts(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                PartNumberMarker=marker,
            )
            parts.update(
                {str(part["PartNumber"]): int(part["Size"]) for part in response.get("Parts", [])}
            )
            if not response.get("IsTruncated"):
                return parts
            marker = int(response["NextPartNumberMarker"])

    def delete(self, key: str, upload_id: str | None = None) -> None:
        if upload_id:
            self.client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_book_storage() -> BookStorage:
    provider = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if provider == "local":
        return LocalBookStorage()
    if provider == "s3":
        return S3BookStorage()
    raise RuntimeError("STORAGE_BACKEND must be either 'local' or 's3'.")
