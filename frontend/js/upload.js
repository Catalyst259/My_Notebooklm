// File upload functionality
class UploadManager {
    constructor() {
        this.isUploading = false;
        this.selectedFiles = [];
    }

    init() {
        const uploadBtn = document.getElementById('uploadBtn');
        const fileInput = document.getElementById('fileInput');
        const uploadZone = document.getElementById('uploadZone');

        // File input change
        fileInput.addEventListener('change', (e) => {
            this.selectedFiles = Array.from(e.target.files);
            this.updateUploadButton();
        });

        // Drag and drop
        uploadZone.addEventListener('click', () => fileInput.click());

        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('drag-over');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('drag-over');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
            this.selectedFiles = Array.from(e.dataTransfer.files);
            this.updateUploadButton();
        });

        uploadBtn.addEventListener('click', () => this.uploadFiles());
    }

    updateUploadButton() {
        const uploadBtn = document.getElementById('uploadBtn');
        if (this.selectedFiles.length === 0) {
            uploadBtn.textContent = '上传文件';
        } else if (this.selectedFiles.length === 1) {
            uploadBtn.textContent = `上传 ${this.selectedFiles[0].name}`;
        } else {
            uploadBtn.textContent = `上传 ${this.selectedFiles.length} 个文件`;
        }
    }

    async uploadFiles() {
        if (this.isUploading || this.selectedFiles.length === 0) return;

        const assistantId = app.currentAssistant?.id;
        if (!assistantId) {
            showToast('请先选择助手', 'error');
            return;
        }

        // Validate extensions
        const allowedExtensions = ['.cpp', '.h', '.txt', '.md', '.pdf', '.docx', '.py', '.c', '.hpp'];
        for (const file of this.selectedFiles) {
            const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
            if (!allowedExtensions.includes(fileExt)) {
                showToast(`不支持的文件格式: ${fileExt}`, 'error');
                return;
            }
        }

        this.isUploading = true;
        const uploadBtn = document.getElementById('uploadBtn');
        const uploadStatus = document.getElementById('uploadStatus');
        const uploadProgress = document.getElementById('uploadProgress');

        uploadBtn.disabled = true;
        uploadBtn.textContent = '上传中...';
        uploadStatus.textContent = `正在上传 ${this.selectedFiles.length} 个文件...`;
        uploadStatus.className = 'status-text info';
        uploadProgress.style.display = 'block';
        uploadProgress.innerHTML = '';

        try {
            const result = await api.uploadFiles(this.selectedFiles, assistantId);

            // Show per-file results
            let successCount = 0;
            let failCount = 0;

            result.results.forEach(r => {
                const item = document.createElement('div');
                item.className = `progress-item ${r.success ? 'success' : 'error'}`;
                item.textContent = r.success
                    ? `✓ ${r.file_name} (${r.chunk_count} 块)`
                    : `✗ ${r.file_name}: ${r.error}`;
                uploadProgress.appendChild(item);

                if (r.success) successCount++;
                else failCount++;
            });

            uploadStatus.textContent = `完成: ${successCount} 成功, ${failCount} 失败`;
            uploadStatus.className = failCount === 0 ? 'status-text success' : 'status-text warning';

            // Clear selection
            this.selectedFiles = [];
            document.getElementById('fileInput').value = '';
            uploadBtn.textContent = '上传文件';

            // Refresh stats and file list
            await app.refreshStats();
            await app.refreshFileList();

            showToast(`上传完成: ${successCount}/${result.results.length}`, 'success');
        } catch (error) {
            console.error('Upload error:', error);
            uploadStatus.textContent = `✗ 上传失败: ${error.message}`;
            uploadStatus.className = 'status-text error';
            showToast('文件上传失败', 'error');
        } finally {
            this.isUploading = false;
            uploadBtn.disabled = false;

            // Hide progress after 5 seconds
            setTimeout(() => {
                uploadProgress.style.display = 'none';
            }, 5000);
        }
    }
}

// Export singleton instance
const uploadManager = new UploadManager();
