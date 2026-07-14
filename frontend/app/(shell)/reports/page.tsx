"use client";

import { useEffect, useState } from "react";
import { Button, Card, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import CreateReportModal, { JOB_ID_STORAGE_KEY } from "@/components/reports/CreateReportModal";
import ReportHistoryTable from "@/components/reports/ReportHistoryTable";

export default function ReportsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  // Nếu còn job_id trong sessionStorage (job đang chạy trước khi F5) — tự mở lại modal
  // ngay khi vào trang, để người dùng thấy trạng thái job + nút Cancel mà không cần
  // tự bấm "Tạo báo cáo" (khôi phục hành vi F5 của bản cũ trước khi tách sang Modal)
  useEffect(() => {
    if (sessionStorage.getItem(JOB_ID_STORAGE_KEY)) {
      setModalOpen(true);
    }
  }, []);

  return (
    <div>
      <Typography.Title level={3}>Báo cáo</Typography.Title>
      <Card
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            Tạo báo cáo
          </Button>
        }
      >
        <ReportHistoryTable reloadToken={reloadToken} />
      </Card>
      <CreateReportModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCompleted={() => setReloadToken((t) => t + 1)}
      />
    </div>
  );
}
