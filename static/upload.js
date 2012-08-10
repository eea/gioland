(function (App) {

	var Upload = function (opts) {

		if (!(this instanceof Upload)) {
		    return new Upload(opts);
		}

		var upload_target = opts['upload_target'];
		var files_target = opts['files_target'];
		var finalize_upload_target = opts['finalize_upload_target'];
		var $container = $(opts['container']);

		var fileAdded = function (file) {
			if(file.fileName.length >= 30) {
				file.fileNameTruncated = file.fileName.substring(0, 27) + '...';
			} else {
				file.fileNameTruncated = file.fileName;
			}
			var html = Mustache.to_html($("#upload-list-template").html(), file);
			$container.find(".files").append(html);
			checkShowHideUploadBtn();
		};

		var fileProgress = function (file) {
			var progress = Math.round(r.progress() * 100);
			var liContainer = $('#' + file.uniqueIdentifier);
			liContainer.find('.bar').css('width', progress + '%');
			liContainer.find('.percentage').text(progress + '%');
		};

		var fileError = function (file, message) {
			var liContainer = $('#' + file.uniqueIdentifier);
			liContainer.find('.progress-bar').hide();
			liContainer.find('.options').show();
			liContainer.find('.err').text(message);
		};

		var removeFile = function (e) {
			e.preventDefault();
			if(confirm('Are you sure you want to cancel this upload ?')) {
				var uid = $(this).parents('li').attr('id');
				var file = r.getFromUniqueIdentifier(uid);
				r.removeFile(file);

				$(this).parents("li").remove();
				checkShowHideUploadBtn();
			}
		};

		var fileSuccess = function (file) {
			var data = {
				resumableFilename: file.file.name,
				resumableTotalSize: file.file.size,
				resumableIdentifier: file.uniqueIdentifier
			};

			var liContainer = $('#' + file.uniqueIdentifier);
			$.post(finalize_upload_target, data, function (response) {
				if(!response || response.status == 'error') {
					liContainer.find('.err').text(response.message);
					return;
				}

				$.get(files_target, function (data) {
					$container.find('.files-table').html(data);
				});
				liContainer.remove();
			});
		};

		var checkShowHideUploadBtn = function () {
			if(r.files.length > 0) {
				$container.find('.upload-btn-container').show();
			} else {
				$container.find('.upload-btn-container').hide();
			}
		};

		var upload = function () {
			$container.find('.options').hide();
			$container.find('.progress-bar').show();
			$container.find('.cancel-btn').show();
			$container.find('.cancel-file').show();

			window.onbeforeunload = confirmPageLeave;
			r.upload();
		};

		var complete = function () {
			$container.find('.upload-btn-container').hide();
			$container.find('.cancel-btn').hide();
			window.onbeforeunload = null;
		};

		var cancel = function (e) {
			e.preventDefault();
			if(confirm('Are you sure you want to cancel all uploads ?')) {
				$.each(r.files, function(i, file) {
					file.cancel();
				});
				$container.find('.upload-container li').remove();
				$container.find('.upload-btn').hide();
				$container.find('.cancel-btn').hide();
			}
		};

		var confirmPageLeave = function (e) {
			if(!e) e = window.event;

			var message = 'Are you sure you want to leave this page?';
		    e.cancelBubble = true;
		    e.returnValue = message;

		    if (e.stopPropagation) {
		        e.stopPropagation();
		        e.preventDefault();
		    }
		    return message;
		};

		var r = new Resumable({target: upload_target});
		if(r.support) {
			r.assignBrowse($container.find('.browse'));
			r.assignDrop($container.find('.droptarget'));
			r.on('fileAdded', fileAdded);
			r.on('fileError', fileError);
			r.on('fileProgress', fileProgress);
			r.on('fileSuccess', fileSuccess);
			r.on('complete', complete);

			$container.on('click', '.file-delete', removeFile);
			$container.on('click', '.upload-btn', upload);
			$container.on('click', '.cancel-btn', cancel);
		} else {
			$container.find('.upload-container').hide();
			$container.find('.upload-container-not-supported').show();
		}
	};

	App.Upload = Upload;

})(App);

