part.bending_lines.append(BendingLine(
    source_ref=proxy.source_ref,
    geometry=LineString([proxy.pts[0], proxy.pts[-1]]),
    length=proxy.length,
    angle_deg=math.degrees(math.atan2(
        proxy.pts[-1][1] - proxy.pts[0][1],
        proxy.pts[-1][0] - proxy.pts[0][0],
    )) % 180,
    part_label=part.label,
))




geom = LineString([proxy.pts[0], proxy.pts[-1]])
part.bending_lines.append(BendingLine(
    source_ref=proxy.source_ref,
    geometry=geom,
    length=proxy.length,
    angle_deg=math.degrees(math.atan2(
        proxy.pts[-1][1] - proxy.pts[0][1],
        proxy.pts[-1][0] - proxy.pts[0][0],
    )) % 180,
    part_label=part.label,
))