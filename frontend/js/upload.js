// File upload functionality
class UploadManager {
    constructor() {
        this.isUploading = false;
    }

    init() {
        const uploadBtn = document.getElementById('uploadBtn');
        const fileInput = document.getElementById('fileInput');

        uploadBtn.addEventListener('click', () => this.uploadFile());
        fileInput.addEventListener('change', () => {
            const uploadBtn = document.getElementById('uploadBtn');
            if (fileInput.files.length > 0) {
                uploadBtn.textContent = `上传 ${fileInput.files[0].name}`;
            } else {
                uploadBtn.textContent = '上传文件';
            }
        });
    }

    async uploadFile() {
        if (this.isUploading) return;

        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];

        if (!file) {
            showToast('请先选择文件', 'error');
            return;
        }

        const assistantId = app.currentAssistant?.id;
        if (!assistantId) {
            showToast('请先选择助手', 'error');
            return;
        }

        // Check file extension
        const allowedExtensions = ['.cpp', '.h', '.txt', '.md', '.pdf', '.docx', '.py', '.c', '.hpp'];
        const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (!allowedExtensions.includes(fileExt)) {
            showToast(`不支持的文件格式: ${fileExt}`, 'error');
            return;
        }

        this.isUploading = true;
        const uploadBtn = document.getElementById('uploadBtn');
        const uploadStatus = document.getElementById('uploadStatus');

        uploadBtn.disabled = true;
        uploadBtn.textContent = '上传中...';
        uploadStatus.textContent = '正在处理文件...';
        uploadStatus.className = 'status-text info';

        try {
            const result = await api.uploadFile(file, assistantId);

            uploadStatus.textContent = `✓ ${result.message} (${result.chunk_count} 个文本块)`;
            uploadStatus.className = 'status-text success';

            // Clear file input
            fileInput.value = '';
            uploadBtn.textContent = '上传文件';

            // Refresh stats
            await app.refreshStats();

            showToast('文件上传成功', 'success');
        } catch (error) {
            console.error('Upload error:', error);
            uploadStatus.textContent = `✗ 上传失败: ${error.message}`;
            uploadStatus.className = 'status-text error';
            showToast('文件上传失败', 'error');
        } finally {
            this.isUploading = false;
            uploadBtn.disabled = false;
        }
    }
}

// Export singleton instance
const uploadManager = new UploadManager();
