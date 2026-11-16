# 客户端资源处理流程

本流程只处理用户已合法取得的本地资源文件，不包含登录、抓包、内存读取或游戏操作脚本。UnityPy 解析 UnityFS 对象，NumPy + Pillow 将预烘焙 Idle 动画绘制为透明 PNG。

1. 将已有客户端 aa 目录打包为 tar（保存内部相对路径和 .lpak 文件）。原始归档、APK、私有运行数据不提交 Git。
2. `python tools/index_archive.py client-aa.tar --output asset-index`：扫描 .lpak 中的 UnityFS 边界，索引 Sprite/Texture2D 的名称、path ID 和资源包位置，输出错误记录。
3. `python tools/export_poses.py client-aa.tar asset-index/inventory.json --output rebuild`：按 tools/profiles.json 的目标模型清单还原姿态。支持 `--only full_Cerberus full_CactusP` 局部重建，不覆盖其他模型。缺失或异常资源输出到 rebuild/extraction-report.json。
4. `python tools/validate_gallery.py rebuild`：验证图片可读、尺寸、无重复记录、等阶一致。人工检查新图，确认没有身体缺失和几何错乱；不能把结构检查当作美术完全还原的证明。
5. 将核验通过的 images 和 gallery.json 更新到网站，保留 profile 分类字段。运行静态服务器，检查筛选、修格和下载后推送。

## 分类依据

profiles.json 保存本次已验证的图片与角色/元素/进化阶段对应关系。原始关联依据是客户端 UnitRes（模型与头像路径）、Pet/UnitElement（元素）、UnitEvolution（品质）。等阶按 UnitRes 的 Evolution 1–4 显示，不将品质颜色当作等阶。未知关系不猜测。profiles 清单是这次客户端版本的结果，新版本需要重新核对，不是通用的游戏解析器。

## 动画还原关键点

通过 gpuAnimData 的 Idle startFrame/textureGroup、MeshHashList、triangleIndexList 取得对应网格与三角形片段。UV1 的顶点编号映射到 half-float 位置贴图，UV0 映射到角色 atlas。材质必须引用 `pbch_gpu_spine_<model>_position_all`，不能用材质名称前缀，否则可能拿到另一进化阶段的贴图。主贴图不在动画资源包时从其所属资源包加载。有被使用的顶点越界就停止导出，不用强行截断掩盖异常。

阴影仅删除可确认的独立、低位、扁平、均匀中性灰网格。换色图用普通 atlas 判断阴影，不按灰色批量删除。非常低 alpha 的远离身体残留会清理。导出静态贴图颜色，并不完整复现着色器、动态发光、渐变与遮罩。刺猬和浣熊等部分布局尚未适配，异常保留在报告中。

## 本次核查

核查 261 个普通模型、346 张换色资源和 70 条臭臭记录。补回 13 张图片，保留正确的阴影处理，去掉重复臭臭记录，更新尺寸元数据。仓库当前包含 604 张塔塔与 69 张臭臭完整姿势。

## 依赖与授权

`python -m pip install -r tools/requirements.txt`。此处 Python 只用于离线资源准备，网站运行无需 Python。UnityPy 使用其自身许可，图纸量化 Worker 的 MIT 许可保留在 vendor 目录。游戏美术版权不属于本项目，MIT 仅覆盖本项目自有代码，不能据此获得游戏资源的再分发或商业授权。
