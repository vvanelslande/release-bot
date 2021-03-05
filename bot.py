# Copyright 2021 Valentin Vanelslande
# Licensed under GPLv3 or any later version
# Refer to the license.txt file included.

import io
import json
import os
import stat
import time
import zipfile

import discord
import discord_slash
import dotenv
import httpx
import py7zr

dotenv.load_dotenv()

client = discord.Client()
bot = discord.ext.commands.Bot('')
slash = discord_slash.SlashCommand(bot, True)


@slash.slash(name='create-draft-release', description='Create a draft release', guild_ids=[812578895701213204])
async def create_draft_release(ctx, repository: str, version: str):
    await ctx.respond(True)

    artifacts = httpx.get(
        httpx.get(
            f'https://api.github.com/repos/vvanelslande/{repository}/actions/runs?per_page=1&status=success',
            headers={
                'Authorization': f'token {os.environ["GITHUB_TOKEN"]}',
                'User-Agent': 'vvanelslande/release-bot'
            }
        ).json()['workflow_runs'][0]['artifacts_url'],
        headers={
            'Authorization': f'token {os.environ["GITHUB_TOKEN"]}',
            'User-Agent': 'vvanelslande/release-bot'
        }
    ).json()['artifacts']

    upload_url = httpx.post(
        f'https://api.github.com/repos/vvanelslande/{repository}/releases',
        headers={
            'Authorization': f'token {os.environ["GITHUB_TOKEN"]}',
            'User-Agent': 'vvanelslande/release-bot'
        },
        json={
            'name': version,
            'tag_name': version,
            'draft': True
        }
    ).json()['upload_url']

    for artifact in artifacts:
        artifact_response = httpx.get(
            artifact['archive_download_url'],
            headers={
                'Authorization': f'token {os.environ["GITHUB_TOKEN"]}',
                'User-Agent': 'vvanelslande/release-bot'
            }
        )

        sz_file_io = io.BytesIO()
        sz_file = py7zr.SevenZipFile(sz_file_io, 'w')

        zip_file_io = io.BytesIO(
            artifact_response.content
        )

        zip_file = zipfile.ZipFile(zip_file_io)
        zip_file_infolist = zip_file.infolist()

        async def upload(bio, is_7z):
            bio_contents = bio.getvalue()

            async def content_function():
                yield bio_contents

            async with httpx.AsyncClient() as client:
                r1 = await client.post(
                    f'{upload_url.replace("{?name,label}", "")}',
                    headers={
                        'Authorization': f'token {os.environ["GITHUB_TOKEN"]}',
                        'User-Agent': 'vvanelslande/release-bot',
                        'Content-Type': 'application/x-7z-compressed' if is_7z else 'application/zip',
                        'Content-Length': str(len(bio_contents))
                    },
                    params={
                        'name': f'{repository}-{version}-{artifact["name"]}.{"7z" if is_7z else "zip"}'
                    },
                    content=content_function()
                )

        if repository == 'vvctre' and artifact['name'] == 'linux':
            zip_file_2_io = io.BytesIO()

            zip_file_2 = zipfile.ZipFile(
                zip_file_2_io,
                'w',
                zipfile.ZIP_DEFLATED
            )

            for info in zip_file_infolist:
                if info.filename == 'vvctre':
                    sz_info = {
                        'origin': None,
                        'data': zip_file.open('vvctre'),
                        'filename': 'vvctre',
                        'uncompressed': 12724264,
                        'emptystream': False,
                        'attributes': (stat.FILE_ATTRIBUTE_ARCHIVE | py7zr.py7zr.FILE_ATTRIBUTE_UNIX_EXTENSION) | (0o100755 << 16),
                        'creationtime': py7zr.helpers.ArchiveTimestamp.from_now(),
                        'lastwritetime': py7zr.helpers.ArchiveTimestamp.from_now()
                    }

                    sz_file.header.files_info.files.append(
                        sz_info
                    )

                    sz_file.header.files_info.emptyfiles.append(
                        sz_info['emptystream']
                    )

                    sz_file.files.append(sz_info)

                    folder = sz_file.header.main_streams.unpackinfo.folders[-1]

                    sz_file.worker.archive(
                        sz_file.fp,
                        sz_file.files,
                        folder,
                        deref=False
                    )

                    zip_info = zipfile.ZipInfo(
                        'vvctre',
                        time.localtime()[:6]
                    )

                    zip_info.compress_type = zipfile.ZIP_DEFLATED
                    zip_info.external_attr = 0o100755 << 16

                    zip_file_2.writestr(
                        zip_info,
                        zip_file.read('vvctre')
                    )
                else:
                    data = zip_file.read(
                        info.filename
                    )

                    sz_file.writestr(
                        data,
                        info.filename
                    )

                    zip_file_2.writestr(
                        info.filename,
                        data
                    )

            sz_file.close()
            zip_file_2.close()

            await upload(sz_file_io, True)
            await upload(zip_file_2_io, False)
        else:
            for info in zip_file_infolist:
                sz_file.writef(
                    zip_file.open(info.filename),
                    info.filename
                )

            sz_file.close()
            zip_file.close()

            await upload(sz_file_io, True)
            await upload(zip_file_io, False)

bot.run(os.environ['DISCORD_TOKEN'])
