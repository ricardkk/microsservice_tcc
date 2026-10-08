-- Transport normalization only; no classification or diagnosis.
function normalize(tag, timestamp, record)
    local attrs = record["attrs"] or {}
    record["service"] = record["service"] or attrs["tcc.service"]
    -- The Loki output removes fields used as labels; use a transport copy.
    record["loki_service"] = record["service"]
    record["timestamp"] = record["timestamp"] or record["time"]
    record["message"] = record["message"] or record["log"]
    record["attrs"] = nil
    record["time"] = nil
    record["log"] = nil
    return 2, timestamp, record
end
