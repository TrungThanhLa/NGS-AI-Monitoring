type Props = {
  collapsed?: boolean;
};

// Logo NGS — vector hoá lại từ ngs-monitoring-ui/frontend/public/logo.svg (không nền,
// khác bản .jpg dùng trước đó có nền trắng đặc). Render inline SVG (không phải <img>)
// để có thể đổi màu tagline — bản gốc dùng #0B2262 (navy đậm) gần trùng màu nền sidebar
// tối (#0A1D55), không đọc được nếu giữ nguyên.
//
// Khối màu + 3 chữ N/G/S dùng chung giữa 2 trạng thái — chỉ khác viewBox (thu gọn cắt bỏ
// tagline + dấu ®) và kích thước hiển thị (width/height tính đúng theo tỉ lệ viewBox,
// tránh bị méo/nhỏ hơn dự kiến do preserveAspectRatio mặc định của SVG).
function Blocks() {
  return (
    <>
      <polygon points="4,8 158,8 140,128 0,128" fill="#0B2262" />
      <polygon points="165,8 318,8 300,128 148,128" fill="#8C95A0" />
      <polygon points="325,8 478,8 460,128 308,128" fill="#00859A" />
      {/* <polygon points="473,8 492,8 492,128 455,128" fill="#00859A" /> */}

      <text x="22" y="110" fontFamily="'Arial Black','Arial'" fontWeight={900} fontSize={108} fontStyle="italic" fill="#FFFFFF">
        N
      </text>
      <text x="180" y="110" fontFamily="'Arial Black','Arial'" fontWeight={900} fontSize={108} fontStyle="italic" fill="#FFFFFF">
        G
      </text>
      <text x="334" y="110" fontFamily="'Arial Black','Arial'" fontWeight={900} fontSize={108} fontStyle="italic" fill="#FFFFFF">
        S
      </text>
    </>
  );
}

export default function Logo({ collapsed }: Props) {
  if (collapsed) {
    // Cắt viewBox chỉ lấy phần 3 khối N/G/S (bỏ dấu ® + tagline — không đủ chỗ khi thu gọn)
    const viewBoxWidth = 492;
    const viewBoxHeight = 136;
    const height = 26;
    const width = Math.round((height * viewBoxWidth) / viewBoxHeight);
    return (
      <svg width={width} height={height} viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`} xmlns="http://www.w3.org/2000/svg">
        <Blocks />
      </svg>
    );
  }

  const viewBoxWidth = 520;
  const viewBoxHeight = 210;
  const height = 64;
  const width = Math.round((height * viewBoxWidth) / viewBoxHeight);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`} xmlns="http://www.w3.org/2000/svg">
      <Blocks />

      <text x="485" y="40" fontFamily="Arial" fontSize={42} fill="#00859A">
        ®
      </text>

      {/* Tagline — đổi màu sang trắng mờ thay vì #0B2262 gốc để đọc được trên nền sidebar tối */}
      <text
        x="4"
        y="178"
        fontFamily="Arial,sans-serif"
        fontWeight={600}
        fontSize={27}
        fill="rgba(255,255,255,0.75)"
        letterSpacing={0.5}
      >
        Minh bạch hóa mọi thông tin
      </text>
    </svg>
  );
}
