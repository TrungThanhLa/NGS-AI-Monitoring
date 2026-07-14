"use client";

import { useState } from "react";
import { Button, Card, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import CreateReportModal from "@/components/reports/CreateReportModal";
import ReportHistoryTable from "@/components/reports/ReportHistoryTable";

export default function ReportsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

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
