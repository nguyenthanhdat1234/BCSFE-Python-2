using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using Test_api.Models;

namespace Test_api.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class BattleCatsApiController : ControllerBase
    {
        private readonly HttpClient _httpClient;
        private readonly string _pythonApiBaseUrl = "http://localhost:5000"; // URL của Flask API

        public BattleCatsApiController(HttpClient httpClient)
        {
            _httpClient = httpClient;
        }

        [HttpPost("ProcessCodes")]
        public async Task<ActionResult<BattleCatsCodeResponse>> ProcessCodes(BattleCatsCodeRequest request)
        {
            if (string.IsNullOrEmpty(request.TransferCode) || string.IsNullOrEmpty(request.ConfirmationCode))
            {
                return BadRequest(new BattleCatsCodeResponse
                {
                    Success = false,
                    Message = "Mã chuyển giao và mã xác nhận là bắt buộc"
                });
            }

            // Tạo FormUrlEncodedContent để gửi đến Python API
            var formContent = new FormUrlEncodedContent(new[]
            {
            new KeyValuePair<string, string>("transfer_code", request.TransferCode),
            new KeyValuePair<string, string>("confirmation_code", request.ConfirmationCode),
            new KeyValuePair<string, string>("country_code", request.CountryCode),
            new KeyValuePair<string, string>("game_version", request.GameVersion)
        });

            try
            {
                // Gọi API Flask
                var response = await _httpClient.PostAsync($"{_pythonApiBaseUrl}/download_from_codes", formContent);

                if (!response.IsSuccessStatusCode)
                {
                    return StatusCode((int)response.StatusCode, new BattleCatsCodeResponse
                    {
                        Success = false,
                        Message = "Lỗi khi gọi API xử lý mã"
                    });
                }

                // Lấy session_id từ Flask (giả sử Flask API đã được sửa đổi để trả về JSON)
                var responseContent = await response.Content.ReadAsStringAsync();
                var flaskResponse = JsonConvert.DeserializeObject<Dictionary<string, object>>(responseContent);

                // Sau khi có session_id, gọi API upload_save để lấy mã mới
                var uploadResponse = await _httpClient.PostAsync(
                    $"{_pythonApiBaseUrl}/edit/upload_save/{flaskResponse["session_id"]}",
                    new StringContent(""));

                var uploadContent = await uploadResponse.Content.ReadAsStringAsync();
                var uploadResult = System.Text.Json.JsonSerializer.Deserialize<Dictionary<string, object>>(uploadContent);

                return Ok(new BattleCatsCodeResponse
                {
                    Success = true,
                    Message = "Xử lý mã thành công",
                    NewTransferCode = uploadResult["transfer_code"].ToString(),
                    NewConfirmationCode = uploadResult["confirmation_code"].ToString(),
                    SaveInfo = flaskResponse.ContainsKey("basic_info")
                        ? (Dictionary<string, object>)flaskResponse["basic_info"]
                        : new Dictionary<string, object>()
                });
            }
            catch (Exception ex)
            {
                return StatusCode(500, new BattleCatsCodeResponse
                {
                    Success = false,
                    Message = $"Lỗi xử lý: {ex.Message}"
                });
            }
        }
        [HttpPost("AutoTransfer")]
        public async Task<ActionResult<BattleCatsAutoTransferResponse>> AutoTransfer(BattleCatsAutoTransferRequest request)
        {
            if (string.IsNullOrEmpty(request.TransferCode) || string.IsNullOrEmpty(request.ConfirmationCode))
            {
                return BadRequest(new BattleCatsAutoTransferResponse
                {
                    Success = false,
                    Message = "Mã chuyển giao và mã xác nhận là bắt buộc"
                });
            }

            try
            {
                // Gọi API Flask để tự động chuyển đổi mã
                var formContent = new FormUrlEncodedContent(new[]
                {
            new KeyValuePair<string, string>("transfer_code", request.TransferCode),
            new KeyValuePair<string, string>("confirmation_code", request.ConfirmationCode),
            new KeyValuePair<string, string>("country_code", request.CountryCode),
            new KeyValuePair<string, string>("game_version", request.GameVersion),
            new KeyValuePair<string, string>("cat_food", request.CatFood?.ToString())
        });

                var response = await _httpClient.PostAsync($"{_pythonApiBaseUrl}/api/auto_transfer", formContent);

                if (!response.IsSuccessStatusCode)
                {
                    return StatusCode((int)response.StatusCode, new BattleCatsAutoTransferResponse
                    {
                        Success = false,
                        Message = $"Lỗi khi gọi API: {response.StatusCode}"
                    });
                }

                var responseContent = await response.Content.ReadAsStringAsync();
                var flaskResult = JsonConvert.DeserializeObject<FlaskAutoTransferResponse>(responseContent);

                if (flaskResult.Status != "success")
                {
                    return BadRequest(new BattleCatsAutoTransferResponse
                    {
                        Success = false,
                        Message = flaskResult.Message
                    });
                }

                // Trả về kết quả
                return Ok(new BattleCatsAutoTransferResponse
                {
                    Success = true,
                    Message = flaskResult.Message,
                    OldTransferCode = request.TransferCode,
                    OldConfirmationCode = request.ConfirmationCode,
                    NewTransferCode = flaskResult.NewTransferCode,
                    NewConfirmationCode = flaskResult.NewConfirmationCode,
                    OriginalValues = new GameValues
                    {
                        CatFood = flaskResult.OriginalValues.CatFood,
                        Xp = flaskResult.OriginalValues.Xp,
                        RareTickets = flaskResult.OriginalValues.RareTickets,
                        PlatinumTickets = flaskResult.OriginalValues.PlatinumTickets
                    },
                    ModifiedValues = new GameValues
                    {
                        CatFood = flaskResult.ModifiedValues.CatFood,
                        Xp = flaskResult.ModifiedValues.Xp,
                        RareTickets = flaskResult.ModifiedValues.RareTickets,
                        PlatinumTickets = flaskResult.ModifiedValues.PlatinumTickets
                    },
                    InquiryCode = flaskResult.InquiryCode
                });
            }
            catch (Exception ex)
            {
                return StatusCode(500, new BattleCatsAutoTransferResponse
                {
                    Success = false,
                    Message = $"Lỗi xử lý: {ex.Message}"
                });
            }
        }
    }


    }
